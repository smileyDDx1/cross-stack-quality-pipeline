FROM mcr.microsoft.com/dotnet/sdk:8.0 AS build
WORKDIR /src
COPY TaskTracker.Api/TaskTracker.Api.csproj TaskTracker.Api/
RUN dotnet restore TaskTracker.Api/TaskTracker.Api.csproj
COPY TaskTracker.Api/ TaskTracker.Api/
RUN dotnet publish TaskTracker.Api/TaskTracker.Api.csproj -c Release -o /app/publish --no-restore

FROM mcr.microsoft.com/dotnet/aspnet:8.0-alpine AS runtime
WORKDIR /app
ENV ASPNETCORE_HTTP_PORTS=8080
EXPOSE 8080
COPY --from=build /app/publish .
USER app
ENTRYPOINT ["dotnet", "TaskTracker.Api.dll"]
