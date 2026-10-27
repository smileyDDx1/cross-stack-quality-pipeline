using System.Security.Claims;
using System.Text;
using Microsoft.IdentityModel.JsonWebTokens;
using Microsoft.IdentityModel.Tokens;
using TaskTracker.Api.Contracts;
using TaskTracker.Api.Models;

namespace TaskTracker.Api.Auth;

public sealed class JwtOptions
{
    public const string Section = "Jwt";

    public string Issuer { get; init; } = "tasktracker";
    public string Audience { get; init; } = "tasktracker-clients";
    public required string Key { get; init; }
    public int ExpiryMinutes { get; init; } = 60;

    public SymmetricSecurityKey SigningKey() => new(Encoding.UTF8.GetBytes(Key));
}

public sealed class TokenService(JwtOptions options, TimeProvider clock)
{
    private readonly JsonWebTokenHandler _handler = new();

    public TokenResponse Issue(User user)
    {
        var now = clock.GetUtcNow().UtcDateTime;
        var descriptor = new SecurityTokenDescriptor
        {
            Issuer = options.Issuer,
            Audience = options.Audience,
            IssuedAt = now,
            NotBefore = now,
            Expires = now.AddMinutes(options.ExpiryMinutes),
            Subject = new ClaimsIdentity(
            [
                new Claim(JwtRegisteredClaimNames.Sub, user.Id.ToString()),
                new Claim(JwtRegisteredClaimNames.Email, user.Email),
                new Claim(JwtRegisteredClaimNames.Name, user.DisplayName),
            ]),
            SigningCredentials = new SigningCredentials(options.SigningKey(), SecurityAlgorithms.HmacSha256),
        };
        return new TokenResponse(_handler.CreateToken(descriptor), "Bearer", options.ExpiryMinutes * 60);
    }
}

public static class ClaimsPrincipalExtensions
{
    public static Guid GetUserId(this ClaimsPrincipal principal) =>
        Guid.Parse(principal.FindFirstValue(JwtRegisteredClaimNames.Sub)
                   ?? throw new InvalidOperationException("Authenticated principal has no subject claim."));
}

public static class TimeProviderExtensions
{
    // Postgres stores microseconds; truncating here keeps create responses identical to later reads.
    public static DateTime UtcNowMicroseconds(this TimeProvider clock)
    {
        var now = clock.GetUtcNow().UtcDateTime;
        return new DateTime(now.Ticks - now.Ticks % 10, DateTimeKind.Utc);
    }

    public static DateOnly UtcToday(this TimeProvider clock) => DateOnly.FromDateTime(clock.GetUtcNow().UtcDateTime);
}
