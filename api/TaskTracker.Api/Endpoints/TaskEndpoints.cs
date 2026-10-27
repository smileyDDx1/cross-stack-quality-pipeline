using System.Security.Claims;
using Microsoft.EntityFrameworkCore;
using TaskTracker.Api.Auth;
using TaskTracker.Api.Contracts;
using TaskTracker.Api.Data;
using TaskTracker.Api.Domain;
using TaskTracker.Api.Models;

namespace TaskTracker.Api.Endpoints;

public static class TaskEndpoints
{
    public static IEndpointRouteBuilder MapTaskEndpoints(this IEndpointRouteBuilder app)
    {
        var projectTasks = app.MapGroup("/api/projects/{projectId:guid}/tasks").WithTags("Tasks").RequireAuthorization();
        projectTasks.MapGet("/", List);
        projectTasks.MapPost("/", Create);

        var tasks = app.MapGroup("/api/tasks").WithTags("Tasks").RequireAuthorization();
        tasks.MapGet("/{id:guid}", Get);
        tasks.MapPatch("/{id:guid}", Update);
        tasks.MapPost("/{id:guid}/status", ChangeStatus);
        tasks.MapDelete("/{id:guid}", Delete);
        return app;
    }

    private static async Task<IResult> List(
        Guid projectId, ClaimsPrincipal principal, AppDbContext db,
        string? status, string? priority, string? search, int? page, int? pageSize, CancellationToken ct)
    {
        var errors = Validators.Paging(page, pageSize);
        TaskState statusFilter = default;
        TaskPriority priorityFilter = default;
        if (status is not null && !ApiEnums.TryParseState(status, out statusFilter))
            errors.Add("status", $"Status must be one of: {string.Join(", ", ApiEnums.StateValues)}.");
        if (priority is not null && !ApiEnums.TryParsePriority(priority, out priorityFilter))
            errors.Add("priority", $"Priority must be one of: {string.Join(", ", ApiEnums.PriorityValues)}.");
        if (errors.HasErrors)
            return Results.ValidationProblem(errors.ToDictionary());

        var ownerId = principal.GetUserId();
        if (!await db.Projects.AnyAsync(p => p.Id == projectId && p.OwnerId == ownerId, ct))
            return ProjectNotFound();

        var query = db.Tasks.AsNoTracking().Where(t => t.ProjectId == projectId);
        if (status is not null)
            query = query.Where(t => t.Status == statusFilter);
        if (priority is not null)
            query = query.Where(t => t.Priority == priorityFilter);
        if (!string.IsNullOrWhiteSpace(search))
            query = query.Where(t => EF.Functions.ILike(t.Title, $"%{EscapeLike(search.Trim())}%", @"\"));

        var (pageNumber, size) = (page ?? 1, pageSize ?? Validators.DefaultPageSize);
        var total = await query.CountAsync(ct);
        var items = await query
            .OrderBy(t => t.CreatedAt).ThenBy(t => t.Id)
            .Skip((pageNumber - 1) * size).Take(size)
            .ToListAsync(ct);

        return Results.Ok(new PagedResponse<TaskResponse>(items.Select(ToResponse).ToList(), pageNumber, size, total));
    }

    private static async Task<IResult> Create(
        Guid projectId, CreateTaskRequest request, ClaimsPrincipal principal, AppDbContext db, TimeProvider clock,
        CancellationToken ct)
    {
        var errors = Validators.CreateTask(request, clock.UtcToday());
        if (errors.HasErrors)
            return Results.ValidationProblem(errors.ToDictionary());

        var ownerId = principal.GetUserId();
        if (!await db.Projects.AnyAsync(p => p.Id == projectId && p.OwnerId == ownerId, ct))
            return ProjectNotFound();

        ApiEnums.TryParsePriority(request.Priority ?? "medium", out var priority);
        var now = clock.UtcNowMicroseconds();
        var task = new TaskItem
        {
            Id = Guid.NewGuid(),
            ProjectId = projectId,
            Title = request.Title!.Trim(),
            Description = string.IsNullOrWhiteSpace(request.Description) ? null : request.Description.Trim(),
            Priority = priority,
            DueDate = request.DueDate,
            CreatedAt = now,
            UpdatedAt = now,
        };
        db.Tasks.Add(task);
        await db.SaveChangesAsync(ct);

        return Results.Created($"/api/tasks/{task.Id}", ToResponse(task));
    }

    private static async Task<IResult> Get(Guid id, ClaimsPrincipal principal, AppDbContext db, CancellationToken ct)
    {
        var task = await FindOwned(db.Tasks.AsNoTracking(), id, principal.GetUserId(), ct);
        return task is null ? TaskNotFound() : Results.Ok(ToResponse(task));
    }

    private static async Task<IResult> Update(
        Guid id, UpdateTaskRequest request, ClaimsPrincipal principal, AppDbContext db, TimeProvider clock,
        CancellationToken ct)
    {
        var errors = Validators.UpdateTask(request, clock.UtcToday());
        if (errors.HasErrors)
            return Results.ValidationProblem(errors.ToDictionary());

        var task = await FindOwned(db.Tasks, id, principal.GetUserId(), ct);
        if (task is null)
            return TaskNotFound();

        // PATCH semantics: fields left out (null) keep their current value.
        if (request.Title is not null)
            task.Title = request.Title.Trim();
        if (request.Description is not null)
            task.Description = string.IsNullOrWhiteSpace(request.Description) ? null : request.Description.Trim();
        if (request.Priority is not null && ApiEnums.TryParsePriority(request.Priority, out var priority))
            task.Priority = priority;
        if (request.DueDate is not null)
            task.DueDate = request.DueDate;
        task.UpdatedAt = clock.UtcNowMicroseconds();

        await db.SaveChangesAsync(ct);
        return Results.Ok(ToResponse(task));
    }

    private static async Task<IResult> ChangeStatus(
        Guid id, ChangeStatusRequest request, ClaimsPrincipal principal, AppDbContext db, TimeProvider clock,
        CancellationToken ct)
    {
        if (!ApiEnums.TryParseState(request.Status, out var target))
        {
            var errors = new ValidationErrors();
            errors.Add("status", $"Status must be one of: {string.Join(", ", ApiEnums.StateValues)}.");
            return Results.ValidationProblem(errors.ToDictionary());
        }

        var task = await FindOwned(db.Tasks, id, principal.GetUserId(), ct);
        if (task is null)
            return TaskNotFound();

        if (!TaskWorkflow.CanTransition(task.Status, target))
        {
            return Results.Problem(
                statusCode: StatusCodes.Status409Conflict,
                title: "Status change not allowed.",
                detail: $"A task cannot move from '{task.Status.ToApi()}' to '{target.ToApi()}'.",
                extensions: new Dictionary<string, object?>
                {
                    ["currentStatus"] = task.Status.ToApi(),
                    ["allowedStatuses"] = TaskWorkflow.AllowedFrom(task.Status).Select(s => s.ToApi()).ToArray(),
                });
        }

        task.Status = target;
        task.UpdatedAt = clock.UtcNowMicroseconds();
        await db.SaveChangesAsync(ct);
        return Results.Ok(ToResponse(task));
    }

    private static async Task<IResult> Delete(Guid id, ClaimsPrincipal principal, AppDbContext db, CancellationToken ct)
    {
        var ownerId = principal.GetUserId();
        var deleted = await db.Tasks.Where(t => t.Id == id && t.Project!.OwnerId == ownerId).ExecuteDeleteAsync(ct);
        return deleted == 0 ? TaskNotFound() : Results.NoContent();
    }

    private static Task<TaskItem?> FindOwned(IQueryable<TaskItem> tasks, Guid id, Guid ownerId, CancellationToken ct) =>
        tasks.FirstOrDefaultAsync(t => t.Id == id && t.Project!.OwnerId == ownerId, ct);

    private static string EscapeLike(string value) =>
        value.Replace(@"\", @"\\").Replace("%", @"\%").Replace("_", @"\_");

    private static TaskResponse ToResponse(TaskItem t) => new(
        t.Id, t.ProjectId, t.Title, t.Description, t.Status.ToApi(), t.Priority.ToApi(), t.DueDate, t.CreatedAt, t.UpdatedAt);

    private static IResult ProjectNotFound() =>
        Results.Problem(statusCode: StatusCodes.Status404NotFound, title: "Project not found.");

    private static IResult TaskNotFound() =>
        Results.Problem(statusCode: StatusCodes.Status404NotFound, title: "Task not found.");
}
