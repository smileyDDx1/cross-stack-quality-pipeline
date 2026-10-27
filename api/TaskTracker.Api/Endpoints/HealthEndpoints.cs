using TaskTracker.Api.Data;

namespace TaskTracker.Api.Endpoints;

public static class HealthEndpoints
{
    public static IEndpointRouteBuilder MapHealthEndpoints(this IEndpointRouteBuilder app)
    {
        app.MapGet("/health", async (AppDbContext db, CancellationToken ct) =>
                await db.Database.CanConnectAsync(ct)
                    ? Results.Ok(new { status = "healthy", database = "up" })
                    : Results.Json(new { status = "unhealthy", database = "down" }, statusCode: StatusCodes.Status503ServiceUnavailable))
            .WithTags("Health");
        return app;
    }
}
