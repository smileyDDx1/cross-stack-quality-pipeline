using TaskTracker.Api.Models;

namespace TaskTracker.Api.Domain;

public static class TaskWorkflow
{
    private static readonly Dictionary<TaskState, TaskState[]> Allowed = new()
    {
        [TaskState.Todo] = [TaskState.InProgress, TaskState.Cancelled],
        [TaskState.InProgress] = [TaskState.Todo, TaskState.Done, TaskState.Cancelled],
        [TaskState.Done] = [TaskState.InProgress],
        [TaskState.Cancelled] = [TaskState.Todo],
    };

    public static IReadOnlyList<TaskState> AllowedFrom(TaskState from) => Allowed[from];

    public static bool CanTransition(TaskState from, TaskState to) => Allowed[from].Contains(to);

    public static bool IsOpen(TaskState state) => state is TaskState.Todo or TaskState.InProgress;
}

public static class ApiEnums
{
    private static readonly Dictionary<TaskState, string> StateNames = new()
    {
        [TaskState.Todo] = "todo",
        [TaskState.InProgress] = "in_progress",
        [TaskState.Done] = "done",
        [TaskState.Cancelled] = "cancelled",
    };

    private static readonly Dictionary<TaskPriority, string> PriorityNames = new()
    {
        [TaskPriority.Low] = "low",
        [TaskPriority.Medium] = "medium",
        [TaskPriority.High] = "high",
    };

    public static IEnumerable<string> StateValues => StateNames.Values;
    public static IEnumerable<string> PriorityValues => PriorityNames.Values;

    public static string ToApi(this TaskState state) => StateNames[state];
    public static string ToApi(this TaskPriority priority) => PriorityNames[priority];

    public static bool TryParseState(string? value, out TaskState state) => TryParse(StateNames, value, out state);
    public static bool TryParsePriority(string? value, out TaskPriority priority) => TryParse(PriorityNames, value, out priority);

    private static bool TryParse<T>(Dictionary<T, string> names, string? value, out T result) where T : struct
    {
        foreach (var (key, name) in names)
        {
            if (string.Equals(name, value?.Trim(), StringComparison.OrdinalIgnoreCase))
            {
                result = key;
                return true;
            }
        }
        result = default;
        return false;
    }
}
