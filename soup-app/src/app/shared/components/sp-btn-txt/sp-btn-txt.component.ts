import { CommonModule } from '@angular/common';
import { Component, EventEmitter, Input, Output } from '@angular/core';

/**
 * Text button, copied from @aledevsharp/sp-lib 1.1.0 (same selector,
 * inputs, output, markup and styles): the library only supports Angular 18.
 * MIT License, Copyright (c) 2024 Alessio Giacché <ale.giacc.dev@gmail.com>
 * @version 1.0
 * @since 1.0.0
 * @author Alessio Giacché
 */
@Component({
  selector: 'sp-btn-txt',
  imports: [CommonModule],
  templateUrl: './sp-btn-txt.component.html',
  styleUrl: './sp-btn-txt.component.scss'
})
export class SpBtnTxtComponent {
  // The button text
  @Input() public text = '';

  // The button color
  @Input() public color = '#ffac1c';

  // If the button is disabled or not
  @Input() public disabled = false;

  // The button cursor
  @Input() public cursor = 'pointer';

  // Handle the output
  @Output() public buttonClick = new EventEmitter<void>();

  /**
   * Click button
   */
  public onClick(): void {
    this.buttonClick.emit();
  }
}
