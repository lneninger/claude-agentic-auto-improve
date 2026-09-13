# .NET 9 Test Playbook

Reusable xUnit + Moq examples for the StockToolScalpingMachine backend. Referenced by `.claude/agents/senior-test-engineer.md`.

---

## Service unit tests (Moq)

```csharp
public class ConditionEvaluationServiceTests
{
    private readonly Mock<IMarketDataProvider> _marketData = new();
    private readonly Mock<IStrategyTimeProvider> _timeProvider = new();
    private readonly Mock<ILogger<ConditionEvaluationService>> _logger = new();
    private readonly ConditionEvaluationService _sut;

    public ConditionEvaluationServiceTests()
    {
        _sut = new ConditionEvaluationService(
            _marketData.Object,
            _timeProvider.Object,
            _logger.Object);
    }

    [Fact]
    public async Task EvaluateAsync_PriceAboveThreshold_ReturnsTrue()
    {
        _marketData.Setup(m => m.GetLastPriceAsync("AAPL", It.IsAny<CancellationToken>()))
                   .ReturnsAsync(155.00m);

        var condition = new PriceCondition
        {
            Symbol = "AAPL",
            Operator = ComparisonOperator.GreaterThan,
            Value = 150.00m
        };

        var result = await _sut.EvaluateAsync(condition, CancellationToken.None);

        Assert.True(result);
    }

    [Theory]
    [InlineData(149.99, false)]
    [InlineData(150.00, false)]
    [InlineData(150.01, true)]
    public async Task EvaluateAsync_GreaterThan_CorrectBoundaryBehavior(decimal price, bool expected)
    {
        _marketData.Setup(m => m.GetLastPriceAsync("AAPL", It.IsAny<CancellationToken>()))
                   .ReturnsAsync(price);

        var condition = new PriceCondition
        {
            Symbol = "AAPL",
            Operator = ComparisonOperator.GreaterThan,
            Value = 150.00m
        };

        var result = await _sut.EvaluateAsync(condition, CancellationToken.None);

        Assert.Equal(expected, result);
    }

    [Fact]
    public async Task EvaluateAsync_MarketDataUnavailable_ReturnsFalseAndLogs()
    {
        _marketData.Setup(m => m.GetLastPriceAsync(It.IsAny<string>(), It.IsAny<CancellationToken>()))
                   .ThrowsAsync(new MarketDataException("Feed unavailable"));

        var condition = new PriceCondition { Symbol = "AAPL", Value = 100m };

        var result = await _sut.EvaluateAsync(condition, CancellationToken.None);

        Assert.False(result);
        _logger.Verify(
            l => l.Log(LogLevel.Error, It.IsAny<EventId>(), It.IsAny<It.IsAnyType>(),
                       It.IsAny<Exception>(), It.IsAny<Func<It.IsAnyType, Exception?, string>>()),
            Times.Once);
    }
}
```

---

## Repository tests with InMemory DB

```csharp
public class StrategyRepositoryTests : IDisposable
{
    private readonly ScalpingMachineDbContext _context;
    private readonly StrategyRepository _sut;

    public StrategyRepositoryTests()
    {
        var options = new DbContextOptionsBuilder<ScalpingMachineDbContext>()
            .UseInMemoryDatabase(Guid.NewGuid().ToString()) // unique DB per test
            .Options;
        _context = new ScalpingMachineDbContext(options);
        _sut = new StrategyRepository(_context);
    }

    [Fact]
    public async Task GetByIdAsync_ExistingStrategy_ReturnsEntity()
    {
        var strategy = CreateStrategy();
        await _context.Strategies.AddAsync(strategy);
        await _context.SaveChangesAsync();

        var result = await _sut.GetByIdAsync(strategy.Id);

        Assert.NotNull(result);
        Assert.Equal(strategy.Name, result.Name);
    }

    [Fact]
    public async Task GetByIdAsync_NonExistent_ReturnsNull()
    {
        var result = await _sut.GetByIdAsync(Guid.NewGuid());
        Assert.Null(result);
    }

    [Fact]
    public async Task DeleteAsync_ExistingStrategy_RemovesFromDatabase()
    {
        var strategy = CreateStrategy();
        await _context.Strategies.AddAsync(strategy);
        await _context.SaveChangesAsync();

        await _sut.DeleteAsync(strategy.Id);

        Assert.Null(await _context.Strategies.FindAsync(strategy.Id));
    }

    private static StrategyDefinition CreateStrategy() => new()
    {
        Id = Guid.NewGuid(),
        Name = "Test Strategy",
        CreatedAt = DateTime.UtcNow
    };

    public void Dispose() => _context.Dispose();
}
```

---

## Controller integration tests (WebApplicationFactory)

```csharp
public class StrategiesControllerTests : IClassFixture<WebApplicationFactory<Program>>
{
    private readonly HttpClient _client;

    public StrategiesControllerTests(WebApplicationFactory<Program> factory)
    {
        _client = factory.WithWebHostBuilder(builder =>
        {
            builder.ConfigureServices(services =>
            {
                var descriptor = services.Single(d => d.ServiceType == typeof(DbContextOptions<ScalpingMachineDbContext>));
                services.Remove(descriptor);
                services.AddDbContext<ScalpingMachineDbContext>(o =>
                    o.UseInMemoryDatabase("IntegrationTest"));
            });
        }).CreateClient();
    }

    [Fact]
    public async Task GetById_ExistingStrategy_Returns200WithData()
    {
        var createResponse = await _client.PostAsJsonAsync("/api/strategies", new { Name = "Test", IsActive = false });
        var created = await createResponse.Content.ReadFromJsonAsync<ApiResponse<StrategyDefinition>>();

        var response = await _client.GetAsync($"/api/strategies/{created!.Data!.Id}");

        response.EnsureSuccessStatusCode();
        var result = await response.Content.ReadFromJsonAsync<ApiResponse<StrategyDefinition>>();
        Assert.True(result!.Success);
        Assert.Equal("Test", result.Data!.Name);
    }

    [Fact]
    public async Task GetById_NonExistentId_Returns404()
    {
        var response = await _client.GetAsync($"/api/strategies/{Guid.NewGuid()}");
        Assert.Equal(HttpStatusCode.NotFound, response.StatusCode);
    }
}
```

---

## Quartz.NET job tests

```csharp
public class StrategyScheduleJobTests
{
    private readonly Mock<IStrategyFlowManager> _flowManager = new();
    private readonly Mock<IJobExecutionContext> _context = new();
    private readonly StrategyScheduleJob _sut;

    public StrategyScheduleJobTests()
    {
        _sut = new StrategyScheduleJob(_flowManager.Object, Mock.Of<ILogger<StrategyScheduleJob>>());
    }

    [Fact]
    public async Task Execute_ValidStrategyId_CallsFlowManager()
    {
        var strategyId = Guid.NewGuid();
        var dataMap = new JobDataMap { ["strategyId"] = strategyId.ToString() };
        _context.Setup(c => c.MergedJobDataMap).Returns(dataMap);
        _context.Setup(c => c.CancellationToken).Returns(CancellationToken.None);

        await _sut.Execute(_context.Object);

        _flowManager.Verify(f => f.ExecuteAsync(strategyId, CancellationToken.None), Times.Once);
    }
}
```
