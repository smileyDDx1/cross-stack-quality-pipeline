using System.Security.Claims;
using Microsoft.AspNetCore.Identity;
using Microsoft.EntityFrameworkCore;
using TaskTracker.Api.Auth;
using TaskTracker.Api.Contracts;
using TaskTracker.Api.Data;
using TaskTracker.Api.Domain;
using TaskTracker.Api.Models;

namespace TaskTracker.Api.Endpoints;

public static class AuthEndpoints
{
    public static IEndpointRouteBuilder MapAuthEndpoints(this IEndpointRouteBuilder app)
    {
        var group = app.MapGroup("/api/auth").WithTags("Auth");
        group.MapPost("/register", Register);
        group.MapPost("/login", Login);
        group.MapGet("/me", Me).RequireAuthorization();
        group.MapDelete("/me", DeleteMe).RequireAuthorization();
        return app;
    }

    private static async Task<IResult> Register(
        RegisterRequest request, AppDbContext db, IPasswordHasher<User> hasher, TimeProvider clock, CancellationToken ct)
    {
        var errors = Validators.Registration(request);
        if (errors.HasErrors)
            return Results.ValidationProblem(errors.ToDictionary());

        var email = NormalizeEmail(request.Email!);
        if (await db.Users.AnyAsync(u => u.Email == email, ct))
            return EmailTaken();

        var user = new User
        {
            Id = Guid.NewGuid(),
            Email = email,
            DisplayName = request.DisplayName!.Trim(),
            CreatedAt = clock.UtcNowMicroseconds(),
        };
        user.PasswordHash = hasher.HashPassword(user, request.Password!);
        db.Users.Add(user);

        try
        {
            await db.SaveChangesAsync(ct);
        }
        catch (DbUpdateException ex) when (ex.IsUniqueViolation())
        {
            return EmailTaken();
        }

        return Results.Created("/api/auth/me", ToResponse(user));
    }

    private static async Task<IResult> Login(
        LoginRequest request, AppDbContext db, IPasswordHasher<User> hasher, TokenService tokens, CancellationToken ct)
    {
        var email = NormalizeEmail(request.Email ?? string.Empty);
        var user = await db.Users.AsNoTracking().FirstOrDefaultAsync(u => u.Email == email, ct);
        if (user is null || string.IsNullOrEmpty(request.Password)
            || hasher.VerifyHashedPassword(user, user.PasswordHash, request.Password) == PasswordVerificationResult.Failed)
        {
            // Same response for unknown email and wrong password, so the endpoint does not reveal which accounts exist.
            return Results.Problem(statusCode: StatusCodes.Status401Unauthorized, title: "Invalid email or password.");
        }

        return Results.Ok(tokens.Issue(user));
    }

    private static async Task<IResult> Me(ClaimsPrincipal principal, AppDbContext db, CancellationToken ct)
    {
        var userId = principal.GetUserId();
        var user = await db.Users.AsNoTracking().FirstOrDefaultAsync(u => u.Id == userId, ct);
        return user is null ? Results.Unauthorized() : Results.Ok(ToResponse(user));
    }

    private static async Task<IResult> DeleteMe(ClaimsPrincipal principal, AppDbContext db, CancellationToken ct)
    {
        var userId = principal.GetUserId();
        var deleted = await db.Users.Where(u => u.Id == userId).ExecuteDeleteAsync(ct);
        return deleted == 0 ? Results.Unauthorized() : Results.NoContent();
    }

    private static string NormalizeEmail(string email) => email.Trim().ToLowerInvariant();

    private static IResult EmailTaken() =>
        Results.Problem(statusCode: StatusCodes.Status409Conflict, title: "Email is already registered.");

    private static UserResponse ToResponse(User user) => new(user.Id, user.Email, user.DisplayName, user.CreatedAt);
}
