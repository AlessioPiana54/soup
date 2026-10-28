import { Injectable } from '@angular/core';
import { Observable, tap } from 'rxjs';

import { OnboardingService } from '../../../../core/v3/onboarding.service';
import { ModalService } from '../../../../shared/components/s-modals/modal.service';

// The first-access hint, with the text of the old dataset page
const FIRST_ACCESS_HINT = {
  title: 'Welcome to SOUP!',
  message: `Thanks for using SOUP. We're happy to have you on board! 🎉

If you’d like to share your thoughts, you can leave feedback using the button at the top right of the Home Page.`,
  button: 'Got it!'
};

/** The first-access hint: a modal the first time an object is ever opened (OnboardingService). */
@Injectable({
  providedIn: 'root'
})
export class FirstAccessHintService {
  /**
   * Constructor for FirstAccessHintService service
   * @param onboarding the OnboardingService service
   * @param modals the ModalService service
   */
  constructor(
    private onboarding: OnboardingService,
    private modals: ModalService
  ) {}

  /** Emits whether this was the first time (and the modal was shown). */
  public showIfFirstTime(): Observable<boolean> {
    return this.onboarding.firstTime().pipe(
      tap((first) => {
        if (first) {
          this.modals.showGenericModal(
            FIRST_ACCESS_HINT.title,
            FIRST_ACCESS_HINT.message,
            false,
            false,
            '',
            FIRST_ACCESS_HINT.button,
            'var(--primary-color)',
            '',
            '',
            () => undefined,
            () => Promise.resolve(),
            () => undefined
          );
        }
      })
    );
  }
}
