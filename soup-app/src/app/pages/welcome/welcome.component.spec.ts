import { ComponentFixture, TestBed } from '@angular/core/testing';
import { Observable, of, throwError } from 'rxjs';

import { Health } from '../../core/v3/v3.models';
import { V3ApiService } from '../../core/v3/v3-api.service';
import { WelcomeComponent } from './welcome.component';

describe('WelcomeComponent', () => {
  let health: () => Observable<Health>;

  async function render(): Promise<ComponentFixture<WelcomeComponent>> {
    await TestBed.configureTestingModule({
      imports: [WelcomeComponent],
      providers: [{ provide: V3ApiService, useValue: { health: () => health() } }]
    }).compileComponents();
    const fixture = TestBed.createComponent(WelcomeComponent);
    fixture.detectChanges();
    return fixture;
  }

  it('shows the state of every tool and the problems', async () => {
    health = () =>
      of({
        status: 'degraded',
        tools: [
          { name: 'memgraph', package: 'tool_memgraph', ok: false, health: {} },
          { name: 'storage', package: 'tool_storage', ok: true, health: {} }
        ],
        problems: ['memgraph: connection refused']
      });
    const text = (await render()).nativeElement.textContent as string;
    expect(text).toContain('Alcuni tool non rispondono');
    expect(text).toContain('memgraph');
    expect(text).toContain('tool_storage');
    expect(text).toContain('connection refused');
  });

  it('says when the Engine is off', async () => {
    health = () => throwError(() => ({ statusCode: 0 }));
    expect((await render()).nativeElement.textContent).toContain('Engine non raggiungibile');
  });
});
