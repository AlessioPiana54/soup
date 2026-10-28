import { Injectable } from '@angular/core';
import { BehaviorSubject, Observable } from 'rxjs';

/**
 * Modals service
 * @version 1.0
 * @since 1.0.0
 * @author Alessio Giacché
 */
@Injectable({
  providedIn: 'root'
})
export class ModalService {
  // The generic modal subject
  private genericModalSubject: BehaviorSubject<any> = new BehaviorSubject<any>(null);

  // The generic modal observable
  public genericModalState: Observable<any> = this.genericModalSubject.asObservable();

  // Initialize a new instance of NotificationService service
  constructor() {}

  /**
   * Show the generic modal
   * @param title the title of the modal
   * @param message the message of the modal
   * @param doubleButton if modal has two buttons
   * @param showInput if we want to include generic input
   * @param inputLabel the label for the input if exist
   * @param primaryButtonText text of primary button
   * @param primaryButtonColor the color of primary button
   * @param secondaryButtonText text of secondary button
   * @param secondaryButtonColor the color of secondary button
   * @param primaryButtonClick function to execute when primary button is clicked
   * @param primaryButtonClickWithInput function to execute when primary button is clicked if exist input
   * @param secondaryButtonClick function to execute when secondary button is clicked
   */
  public showGenericModal(
    title: string,
    message: string,
    doubleButton: boolean,
    showInput: boolean,
    inputLabel: string,
    primaryButtonText: string,
    primaryButtonColor: string,
    secondaryButtonText: string,
    secondaryButtonColor: string,
    primaryButtonClick: () => void,
    primaryButtonClickWithInput: (value: any) => Promise<any> | null,
    secondaryButtonClick: (() => void) | null
  ) {
    this.genericModalSubject.next({
      title,
      message,
      doubleButton,
      showInput,
      inputLabel,
      primaryButtonText,
      primaryButtonColor,
      secondaryButtonText,
      secondaryButtonColor,
      primaryButtonClick,
      primaryButtonClickWithInput,
      secondaryButtonClick
    });
  }

  /**
   * Hide the generic modal
   */
  public hideGenericModal() {
    this.genericModalSubject.next(null);
  }
}
