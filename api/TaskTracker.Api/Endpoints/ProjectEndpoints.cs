using System.Linq.Expressions;
using System.Security.Claims;
using Microsoft.EntityFrameworkCore;
using TaskTracker.Api.Auth;
using TaskTracker.Api.Contracts;
using TaskTracker.Api.Data;
using TaskTracker.Api.Domain;
using TaskTracker.Api.Models;

namespace TaskTracker.Api.Endpoints;

public static class ProjectEndpoints
{
    // Translated by EF Core into a single SQL statement with correlated COUNT subqueries.
    private static readonly Expression<Func<Project, ProjectResponse>> ToResponse = p => new ProjectResponse(
        p.Id,
        p.Name,
        p.Description,
        p.Tasks.Count(),
        p.Tasks.Count(t => t.Status == TaskState.Todo || t.Status == TaskState.InProgress),
        p.CreatedAt,
        p.UpdatedAt);

    private static readonly Func<Project, ProjectResponse> ToResponseInMemory = ToResponse.Compile();

    public static IEndpointRouteBuilder MapProjectEndpoints(this IEndpointRouteBuilder app)
    {
        var group = app.MapGroup("/api/projects").WithTags("Projects").RequireAuthorization();
        group.MapGet("/", List);
        group.MapPost("/", Create);
        group.MapGet("/{id:guid}", Get);
        group.MapPut("/{id:guid}", Update);
        group.MapDelete("/{id:guid}", Delete);
        return app;
    }

    private static async Task<IResult> List(
        ClaimsPrincipal principal, AppDbContext db, int? page, int? pageSize, CancellationToken ct)
    {
        var errors = Validators.Paging(page, pageSize);
        if (errors.HasErrors)
            return Results.ValidationProblem(errors.ToDictionary());

        var (pageNumber, size) = (page ?? 1, pageSize ?? Validators.DefaultPageSize);
        var ownerId = principal.GetUserId();
        var owned = db.Projects.AsNoTracking().Where(p => p.OwnerId == ownerId);

        var total = await owned.CountAsync(ct);
        // Counts are computed in the same statement as the page itself. Counting per project in a loop
        // cost 2 extra round trips per row (42 statements for a 20-row page) and was the dashboard's bottleneck.
        var items = await owned
            .OrderBy(p => p.CreatedAt).ThenBy(p => p.Id)
            .Skip((pageNumber - 1) * size).Take(size)
            .Select(ToResponse)
            .ToListAsync(ct);

        return Results.Ok(new PagedResponse<ProjectResponse>(items, pageNumber, size, total));
    }

    private static async Task<IResult> Get(Guid id, ClaimsPrincipal principal, AppDbContext db, CancellationToken ct)
    {
        var project = await FindResponse(db, id, principal.GetUserId(), ct);
        return project is null ? NotFound() : Results.Ok(project);
    }

    private static async Task<IResult> Create(
        ProjectRequest request, ClaimsPrincipal principal, AppDbContext db, TimeProvider clock, CancellationToken ct)
    {
        var errors = Validators.Project(request);
        if (errors.HasErrors)
            return Results.ValidationProblem(errors.ToDictionary());

        var ownerId = principal.GetUserId();
        var name = request.Name!.Trim();
        if (await db.Projects.AnyAsync(p => p.OwnerId == ownerId && p.Name == name, ct))
            return NameTaken(name);

        var now = clock.UtcNowMicroseconds();
        var project = new Project
        {
            Id = Guid.NewGuid(),
            OwnerId = ownerId,
            Name = name,
            Description = NullIfBlank(request.Description),
            CreatedAt = now,
            UpdatedAt = now,
        };
        db.Projects.Add(project);

        try
        {
            await db.SaveChangesAsync(ct);
        }
        catch (DbUpdateException ex) when (ex.IsUniqueViolation())
        {
            // Two concurrent creates can both pass the AnyAsync check; the unique index decides the winner.
            return NameTaken(name);
        }

        return Results.Created($"/api/projects/{project.Id}", ToResponseInMemory(project));
    }

    private static async Task<IResult> Update(
        Guid id, ProjectRequest request, ClaimsPrincipal principal, AppDbContext db, TimeProvider clock, CancellationToken ct)
    {
        var errors = Validators.Project(request);
        if (errors.HasErrors)
            return Results.ValidationProblem(errors.ToDictionary());

        var ownerId = principal.GetUserId();
        var project = await db.Projects.FirstOrDefaultAsync(p => p.Id == id && p.OwnerId == ownerId, ct);
        if (project is null)
            return NotFound();

        var name = request.Name!.Trim();
        if (await db.Projects.AnyAsync(p => p.OwnerId == ownerId && p.Name == name && p.Id != id, ct))
            return NameTaken(name);

        project.Name = name;
        project.Description = NullIfBlank(request.Description);
        project.UpdatedAt = clock.UtcNowMicroseconds();

        try
        {
            await db.SaveChangesAsync(ct);
        }
        catch (DbUpdateException ex) when (ex.IsUniqueViolation())
        {
            return NameTaken(name);
        }

        return Results.Ok(await FindResponse(db, id, ownerId, ct));
    }

    private static async Task<IResult> Delete(Guid id, ClaimsPrincipal principal, AppDbContext db, CancellationToken ct)
    {
        var ownerId = principal.GetUserId();
        var deleted = await db.Projects.Where(p => p.Id == id && p.OwnerId == ownerId).ExecuteDeleteAsync(ct);
        return deleted == 0 ? NotFound() : Results.NoContent();
    }

    private static Task<ProjectResponse?> FindResponse(AppDbContext db, Guid id, Guid ownerId, CancellationToken ct) =>
        db.Projects.AsNoTracking()
            .Where(p => p.Id == id && p.OwnerId == ownerId)
            .Select(ToResponse)
            .FirstOrDefaultAsync(ct);

    private static string? NullIfBlank(string? value) => string.IsNullOrWhiteSpace(value) ? null : value.Trim();

    // Another user's project is reported as missing rather than forbidden, so ids cannot be probed.
    private static IResult NotFound() =>
        Results.Problem(statusCode: StatusCodes.Status404NotFound, title: "Project not found.");

    private static IResult NameTaken(string name) =>
        Results.Problem(statusCode: StatusCodes.Status409Conflict, title: "Project name already in use.",
            detail: $"You already have a project named '{name}'.");
}
