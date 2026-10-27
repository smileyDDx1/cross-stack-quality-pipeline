using System.Text.RegularExpressions;
using TaskTracker.Api.Contracts;

namespace TaskTracker.Api.Domain;

public sealed class ValidationErrors
{
    private readonly Dictionary<string, List<string>> _errors = new();

    public bool HasErrors => _errors.Count > 0;

    public void Add(string field, string message)
    {
        if (!_errors.TryGetValue(field, out var messages))
        {
            messages = [];
            _errors[field] = messages;
        }
        messages.Add(message);
    }

    public bool Has(string field) => _errors.ContainsKey(field);

    public Dictionary<string, string[]> ToDictionary() => _errors.ToDictionary(e => e.Key, e => e.Value.ToArray());
}

public static partial class Validators
{
    public const int MaxEmail = 254;
    public const int MinPassword = 8;
    public const int MaxPassword = 128;
    public const int MaxDisplayName = 100;
    public const int MaxProjectName = 100;
    public const int MaxProjectDescription = 1000;
    public const int MaxTaskTitle = 200;
    public const int MaxTaskDescription = 4000;
    public const int MaxPage = 100_000;
    public const int MaxPageSize = 100;
    public const int DefaultPageSize = 20;

    [GeneratedRegex(@"^[^@\s]+@[^@\s]+\.[^@\s]+$")]
    private static partial Regex EmailPattern();

    public static ValidationErrors Registration(RegisterRequest request)
    {
        var errors = new ValidationErrors();
        var email = request.Email?.Trim();
        if (string.IsNullOrEmpty(email))
            errors.Add("email", "Email is required.");
        else if (email.Length > MaxEmail || !EmailPattern().IsMatch(email))
            errors.Add("email", "Email is not a valid address.");

        var password = request.Password ?? string.Empty;
        if (password.Length < MinPassword || password.Length > MaxPassword)
            errors.Add("password", $"Password must be {MinPassword}-{MaxPassword} characters.");
        if (!password.Any(char.IsLetter) || !password.Any(char.IsDigit))
            errors.Add("password", "Password must contain at least one letter and one digit.");

        RequiredText(errors, "displayName", "Display name", request.DisplayName, MaxDisplayName);
        return errors;
    }

    public static ValidationErrors Project(ProjectRequest request)
    {
        var errors = new ValidationErrors();
        RequiredText(errors, "name", "Name", request.Name, MaxProjectName);
        OptionalText(errors, "description", "Description", request.Description, MaxProjectDescription);
        return errors;
    }

    public static ValidationErrors CreateTask(CreateTaskRequest request, DateOnly today)
    {
        var errors = new ValidationErrors();
        RequiredText(errors, "title", "Title", request.Title, MaxTaskTitle);
        OptionalText(errors, "description", "Description", request.Description, MaxTaskDescription);
        Priority(errors, request.Priority);
        DueDate(errors, request.DueDate, today);
        return errors;
    }

    public static ValidationErrors UpdateTask(UpdateTaskRequest request, DateOnly today)
    {
        var errors = new ValidationErrors();
        if (request.Title is not null)
            RequiredText(errors, "title", "Title", request.Title, MaxTaskTitle);
        OptionalText(errors, "description", "Description", request.Description, MaxTaskDescription);
        Priority(errors, request.Priority);
        DueDate(errors, request.DueDate, today);
        return errors;
    }

    public static ValidationErrors Paging(int? page, int? pageSize)
    {
        var errors = new ValidationErrors();
        if (page is < 1 or > MaxPage)
            errors.Add("page", $"Page must be between 1 and {MaxPage}.");
        if (pageSize is < 1 or > MaxPageSize)
            errors.Add("pageSize", $"Page size must be between 1 and {MaxPageSize}.");
        return errors;
    }

    private static void RequiredText(ValidationErrors errors, string field, string label, string? value, int max)
    {
        var trimmed = value?.Trim();
        if (string.IsNullOrEmpty(trimmed))
            errors.Add(field, $"{label} is required.");
        else if (trimmed.Length > max)
            errors.Add(field, $"{label} must be at most {max} characters.");
    }

    private static void OptionalText(ValidationErrors errors, string field, string label, string? value, int max)
    {
        if (value is not null && value.Trim().Length > max)
            errors.Add(field, $"{label} must be at most {max} characters.");
    }

    private static void Priority(ValidationErrors errors, string? priority)
    {
        if (priority is not null && !ApiEnums.TryParsePriority(priority, out _))
            errors.Add("priority", $"Priority must be one of: {string.Join(", ", ApiEnums.PriorityValues)}.");
    }

    private static void DueDate(ValidationErrors errors, DateOnly? dueDate, DateOnly today)
    {
        if (dueDate is { } due && due < today)
            errors.Add("dueDate", "Due date cannot be in the past.");
    }
}
