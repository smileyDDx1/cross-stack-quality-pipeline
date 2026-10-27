namespace TaskTracker.Api.Contracts;

// Enum-valued fields travel as strings so that bad values come back as field-level validation errors.

public record RegisterRequest(string? Email, string? Password, string? DisplayName);

public record LoginRequest(string? Email, string? Password);

public record UserResponse(Guid Id, string Email, string DisplayName, DateTime CreatedAt);

public record TokenResponse(string AccessToken, string TokenType, int ExpiresIn);

public record ProjectRequest(string? Name, string? Description);

public record ProjectResponse(
    Guid Id,
    string Name,
    string? Description,
    int TaskCount,
    int OpenTaskCount,
    DateTime CreatedAt,
    DateTime UpdatedAt);

public record CreateTaskRequest(string? Title, string? Description, string? Priority, DateOnly? DueDate);

public record UpdateTaskRequest(string? Title, string? Description, string? Priority, DateOnly? DueDate);

public record ChangeStatusRequest(string? Status);

public record TaskResponse(
    Guid Id,
    Guid ProjectId,
    string Title,
    string? Description,
    string Status,
    string Priority,
    DateOnly? DueDate,
    DateTime CreatedAt,
    DateTime UpdatedAt);

public record PagedResponse<T>(IReadOnlyList<T> Items, int Page, int PageSize, int Total);
