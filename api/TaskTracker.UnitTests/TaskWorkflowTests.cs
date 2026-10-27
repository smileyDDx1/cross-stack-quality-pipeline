using TaskTracker.Api.Domain;
using TaskTracker.Api.Models;

namespace TaskTracker.UnitTests;

// The full transition matrix lives here: it is pure logic, so every pair is cheap to check.
// The Python API suite only checks that the 409 contract is wired up for one illegal move.
public class TaskWorkflowTests
{
    public static TheoryData<TaskState, TaskState, bool> Transitions()
    {
        var allowed = new HashSet<(TaskState, TaskState)>
        {
            (TaskState.Todo, TaskState.InProgress),
            (TaskState.Todo, TaskState.Cancelled),
            (TaskState.InProgress, TaskState.Todo),
            (TaskState.InProgress, TaskState.Done),
            (TaskState.InProgress, TaskState.Cancelled),
            (TaskState.Done, TaskState.InProgress),
            (TaskState.Cancelled, TaskState.Todo),
        };

        var data = new TheoryData<TaskState, TaskState, bool>();
        foreach (var from in Enum.GetValues<TaskState>())
        foreach (var to in Enum.GetValues<TaskState>())
            data.Add(from, to, allowed.Contains((from, to)));
        return data;
    }

    [Theory]
    [MemberData(nameof(Transitions))]
    public void CanTransition_matches_the_workflow(TaskState from, TaskState to, bool expected) =>
        Assert.Equal(expected, TaskWorkflow.CanTransition(from, to));

    [Theory]
    [InlineData(TaskState.Todo, true)]
    [InlineData(TaskState.InProgress, true)]
    [InlineData(TaskState.Done, false)]
    [InlineData(TaskState.Cancelled, false)]
    public void IsOpen_counts_only_unfinished_states(TaskState state, bool expected) =>
        Assert.Equal(expected, TaskWorkflow.IsOpen(state));

    [Theory]
    [InlineData("todo", TaskState.Todo)]
    [InlineData("IN_PROGRESS", TaskState.InProgress)]
    [InlineData(" done ", TaskState.Done)]
    public void Status_names_parse_case_insensitively(string value, TaskState expected)
    {
        Assert.True(ApiEnums.TryParseState(value, out var state));
        Assert.Equal(expected, state);
    }

    [Theory]
    [InlineData("InProgress")]
    [InlineData("finished")]
    [InlineData("")]
    [InlineData(null)]
    public void Unknown_status_names_are_rejected(string? value) =>
        Assert.False(ApiEnums.TryParseState(value, out _));
}
