import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideNoopAnimations } from '@angular/platform-browser/animations';

import { SToastComponent } from './s-toast.component';

describe('SToastComponent', () => {
  let component: SToastComponent;
  let fixture: ComponentFixture<SToastComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [SToastComponent],
      providers: [provideNoopAnimations()]
    }).compileComponents();

    fixture = TestBed.createComponent(SToastComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
