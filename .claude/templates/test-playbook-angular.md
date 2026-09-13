# Angular 21 Test Playbook

Reusable Jasmine + Karma examples for this project's frontend — the applications named by the `frontend.roots` slot of `.claude/project-profile.md`. Referenced by `.claude/agents/senior-test-engineer.md`.

---

## Testing signal-based state services

```typescript
describe('StrategyState', () => {
  let state: StrategyState;

  beforeEach(() => {
    TestBed.configureTestingModule({});
    state = TestBed.inject(StrategyState);
  });

  it('items_initiallyEmpty_returnsEmptyArray', () => {
    expect(state.items()).toEqual([]);
  });

  it('setItems_validList_updatesSignal', () => {
    const strategies = [mockStrategy({ id: '1' }), mockStrategy({ id: '2' })];
    state.setItems(strategies);
    expect(state.items()).toEqual(strategies);
    expect(state.items().length).toBe(2);
  });

  it('update_existingId_replacesItem', () => {
    const original = mockStrategy({ id: '1', name: 'Old' });
    const updated = mockStrategy({ id: '1', name: 'New' });
    state.setItems([original]);
    state.update(updated);
    expect(state.items()[0].name).toBe('New');
  });

  it('update_nonExistentId_leavesListUnchanged', () => {
    const item = mockStrategy({ id: '1' });
    state.setItems([item]);
    state.update(mockStrategy({ id: '999' }));
    expect(state.items().length).toBe(1);
  });

  it('remove_existingId_removesItem', () => {
    state.setItems([mockStrategy({ id: '1' }), mockStrategy({ id: '2' })]);
    state.remove('1');
    expect(state.items().map(s => s.id)).toEqual(['2']);
  });

  it('activeCount_computedCorrectly_whenMixedActiveStatus', () => {
    state.setItems([
      mockStrategy({ id: '1', isActive: true }),
      mockStrategy({ id: '2', isActive: false }),
      mockStrategy({ id: '3', isActive: true }),
    ]);
    expect(state.activeCount()).toBe(2);
  });

  it('clear_resetsAllSignals', () => {
    state.setItems([mockStrategy({ id: '1' })]);
    state.setLoading(true);
    state.clear();
    expect(state.items()).toEqual([]);
    expect(state.loading()).toBeFalse();
  });
});
```

---

## Testing services with HttpClient

```typescript
describe('StrategyService', () => {
  let service: StrategyService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClientTesting()]
    });
    service = TestBed.inject(StrategyService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => httpMock.verify());

  it('getAll_onSuccess_returnsApiResponse', () => {
    const expected: ApiResponseOf<StrategyDefinition[]> = {
      success: true,
      data: [mockStrategy()],
      error: null
    };

    service.getAll().subscribe(res => {
      expect(res.success).toBeTrue();
      expect(res.data!.length).toBe(1);
    });

    const req = httpMock.expectOne(`${environment.apiUrl}/strategies`);
    expect(req.request.method).toBe('GET');
    req.flush(expected);
  });

  it('create_sendsPayloadWithoutId', () => {
    const strategy = mockStrategy({ id: 'client-id' });

    service.create(strategy).subscribe();

    const req = httpMock.expectOne(`${environment.apiUrl}/strategies`);
    expect(req.request.body).not.toHaveProperty('id', 'client-id');
    req.flush({ success: true, data: { ...strategy, id: 'server-id' } });
  });

  it('delete_callsCorrectEndpointWithMethod', () => {
    service.delete('abc-123').subscribe();
    const req = httpMock.expectOne(`${environment.apiUrl}/strategies/abc-123`);
    expect(req.request.method).toBe('DELETE');
    req.flush({ success: true });
  });
});
```

---

## Testing components with signals

```typescript
describe('StrategyListComponent', () => {
  let fixture: ComponentFixture<StrategyListComponent>;
  let state: StrategyState;
  let mockService: jasmine.SpyObj<StrategyService>;

  beforeEach(async () => {
    mockService = jasmine.createSpyObj('StrategyService', ['getAll', 'delete']);
    mockService.getAll.and.returnValue(of({ success: true, data: [] }));

    await TestBed.configureTestingModule({
      imports: [StrategyListComponent, NoopAnimationsModule],
      providers: [{ provide: StrategyService, useValue: mockService }]
    }).compileComponents();

    fixture = TestBed.createComponent(StrategyListComponent);
    state = TestBed.inject(StrategyState);
    fixture.detectChanges();
  });

  it('showsLoadingSpinner_whileLoadingIsTrue', () => {
    state.setLoading(true);
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('mat-spinner')).toBeTruthy();
  });

  it('showsEmptyState_whenNoStrategiesAndNotLoading', () => {
    state.setItems([]);
    state.setLoading(false);
    fixture.detectChanges();
    const emptyEl = fixture.nativeElement.querySelector('[data-testid="empty-state"]');
    expect(emptyEl).toBeTruthy();
  });

  it('rendersStrategyCards_forEachItemInState', () => {
    state.setItems([mockStrategy({ id: '1' }), mockStrategy({ id: '2' })]);
    fixture.detectChanges();
    const cards = fixture.nativeElement.querySelectorAll('[data-testid="strategy-card"]');
    expect(cards.length).toBe(2);
  });
});
```

---

## Testing SignalR integration

```typescript
describe('NotificationCenter SignalR', () => {
  let mockSignalR: jasmine.SpyObj<SignalrService>;
  const subject = new Subject<Notification>();

  beforeEach(async () => {
    mockSignalR = jasmine.createSpyObj('SignalrService', ['on']);
    mockSignalR.on.and.returnValue(subject.asObservable());

    await TestBed.configureTestingModule({
      imports: [NotificationCenterComponent, NoopAnimationsModule],
      providers: [{ provide: SignalrService, useValue: mockSignalR }]
    }).compileComponents();
  });

  it('addsNotification_whenSignalREventReceived', () => {
    const fixture = TestBed.createComponent(NotificationCenterComponent);
    fixture.detectChanges();

    subject.next(mockNotification({ id: 'n1', message: 'Test' }));
    fixture.detectChanges();

    expect(fixture.componentInstance.notifications().length).toBe(1);
  });
});
```
