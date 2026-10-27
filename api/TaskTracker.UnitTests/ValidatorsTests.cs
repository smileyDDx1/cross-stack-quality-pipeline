using TaskTracker.Api.Contracts;
using TaskTracker.Api.Domain;

namespace TaskTracker.UnitTests;

public class ValidatorsTests
{
    private static readonly DateOnly Today = new(2026, 10, 27);

    [Theory]
    [InlineData("short1")]
    [InlineData("onlyletters")]
    [InlineData("12345678")]
    public void Weak_passwords_are_rejected(string password)
    {
        var errors = Validators.Registration(new RegisterRequest("qa@example.test", password, "QA"));
        Assert.True(errors.Has("password"));
    }

    [Theory]
    [InlineData("not-an-email")]
    [InlineData("missing-domain@")]
    [InlineData("no-tld@example")]
    [InlineData("spaces in@example.test")]
    public void Malformed_emails_are_rejected(string email)
    {
        var errors = Validators.Registration(new RegisterRequest(email, "Passw0rd!", "QA"));
        Assert.True(errors.Has("email"));
    }

    [Fact]
    public void Valid_registration_has_no_errors()
    {
        var errors = Validators.Registration(new RegisterRequest(" QA@Example.test ", "Passw0rd!", "QA"));
        Assert.False(errors.HasErrors);
    }

    [Theory]
    [InlineData(100, false)]
    [InlineData(101, true)]
    public void Project_name_length_boundary(int length, bool expectError)
    {
        var errors = Validators.Project(new ProjectRequest(new string('a', length), null));
        Assert.Equal(expectError, errors.Has("name"));
    }

    [Theory]
    [InlineData("")]
    [InlineData("   ")]
    [InlineData(null)]
    public void Project_name_is_required(string? name) =>
        Assert.True(Validators.Project(new ProjectRequest(name, null)).Has("name"));

    [Fact]
    public void Due_date_today_is_allowed_but_yesterday_is_not()
    {
        Assert.False(Validators.CreateTask(new CreateTaskRequest("t", null, null, Today), Today).HasErrors);
        Assert.True(Validators.CreateTask(new CreateTaskRequest("t", null, null, Today.AddDays(-1)), Today).Has("dueDate"));
    }

    [Fact]
    public void Unknown_priority_is_rejected() =>
        Assert.True(Validators.CreateTask(new CreateTaskRequest("t", null, "urgent", null), Today).Has("priority"));

    [Fact]
    public void Patch_with_no_fields_is_valid() =>
        Assert.False(Validators.UpdateTask(new UpdateTaskRequest(null, null, null, null), Today).HasErrors);

    [Fact]
    public void Patch_cannot_blank_the_title() =>
        Assert.True(Validators.UpdateTask(new UpdateTaskRequest("  ", null, null, null), Today).Has("title"));

    [Theory]
    [InlineData(0, null, "page")]
    [InlineData(null, 0, "pageSize")]
    [InlineData(null, 101, "pageSize")]
    public void Paging_bounds(int? page, int? pageSize, string field) =>
        Assert.True(Validators.Paging(page, pageSize).Has(field));
}
