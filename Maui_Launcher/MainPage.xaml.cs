using System.Numerics;

namespace Maui_Launcher
{
    public partial class MainPage : ContentPage
    {
        private ICursorController _cursorController;                            //DEBUGGING: creates a cursor controller


        public MainPage()
        {
            InitializeComponent();

            _cursorController = CreateCursorController();                       //DEBUGGING: create the cursor controller

        }


        //Cursor setup
        public interface ICursorController                                      //DEBUGGING: defines the cursor controller interface type
        {
            Vector2 CursorPosition { get; }
            Task SetCursorPositionAsync(Vector2 position);
        }
        private ICursorController CreateCursorController()                      //DEBUGGING: method called to create the instantiation of the CursorController class
        {
            return new CursorController();
        }
        public class CursorController : ICursorController
        {
            private readonly Vector2 _minPosition = new(0.0f, 0.0f);
            private readonly Vector2 _maxPosition = new(1.0f, 1.0f);

            public Vector2 CursorPosition { get; private set; } = new(0.5f, 0.5f);

            public Task SetCursorPositionAsync(Vector2 position)
            {
                float clampedX = Math.Clamp(position.X, _minPosition.X, _maxPosition.X);
                float clampedY = Math.Clamp(position.Y, _minPosition.Y, _maxPosition.Y);
                CursorPosition = new Vector2(clampedX, clampedY);

                Console.WriteLine($"Cursor position set to: ({clampedX:F2}, {clampedY:F2})");
                return Task.CompletedTask;
            }
        }
        //Cursor position update
        private void UpdateCursorPointerPosition()
        {
            const double imageWidth = 300;
            const double imageHeight = 200;
            const double pointerSize = 50;                                      //SET the variable to the same value as the CursorPointer width/height in the xaml page.

            Vector2 pos = _cursorController?.CursorPosition ?? new Vector2(0.5f, 0.5f);

            double xOffset = pos.X * imageWidth - pointerSize / 2;
            double yOffset = pos.Y * imageHeight - pointerSize / 2;

            if (CursorPointer != null)
            {
                CursorPointer.TranslationX = xOffset;
                CursorPointer.TranslationY = yOffset;
            }
        }


        /*DEBUGGING*/

        /*DEBUGGING - change position of cursor based on sliders in the xaml page*/
        private async void CursorXPosition_ValueChanged(object sender, ValueChangedEventArgs e)
        {
            if (_cursorController != null)
            {
                var newPosition = new Vector2((float)e.NewValue, _cursorController.CursorPosition.Y);
                await _cursorController.SetCursorPositionAsync(newPosition); UpdateCursorPointerPosition();
                UpdateCursorPointerPosition();
            }
            // Update label to show current zoom level
            CursorXPositionLabel.Text = _cursorController != null
                ? $"XPosition of cursor: {_cursorController.CursorPosition.X:F2}"
                : "Cursor controller not initialized.";
        }
        private async void CursorYPosition_ValueChanged(object sender, ValueChangedEventArgs e)
        {
            if (_cursorController != null)
            {
                var newPosition = new Vector2(_cursorController.CursorPosition.X, (float)e.NewValue);
                await _cursorController.SetCursorPositionAsync(newPosition);
                UpdateCursorPointerPosition();
            }
            // Update label to show current zoom level
            CursorYPositionLabel.Text = _cursorController != null
                ? $"YPosition of cursor: {_cursorController.CursorPosition.Y:F2}"
                : "Cursor controller not initialized.";
        }



    }
}
