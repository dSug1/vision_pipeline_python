using System.Diagnostics;
using System.Numerics;

namespace MauiApp_Launcher
{
    public partial class MainPage : ContentPage
    {
        private ICursorController _cursorController;                            //DEBUGGING: creates a cursor controller


        public MainPage()
        {
            InitializeComponent();

            _cursorController = CreateCursorController();                       //DEBUGGING: create the cursor controller
        }

        // Client setup
        /* WARNING: make sure the Python Server is already launched & is therefore listening */
        protected override async void OnAppearing()                             //create the Client connection when the page is loaded. The Server should already be listening
        {
            base.OnAppearing();

            var client = new Client("127.0.0.1", 5050);
            await client.ConnectAsync();
            Debug.WriteLine("client launched");
        }


        //Cursor setup
        private ICursorController CreateCursorController()                      //DEBUGGING: method called to create the instantiation of the CursorController class
        {
            Vector2 pointerSize = GetPointerSize();
            return new CursorController(pointerSize);
        }

        private Vector2 GetPointerSize()
        {
            return new Vector2((float)CursorPointer.WidthRequest, (float)CursorPointer.HeightRequest);
        }

        //Cursor position update
        private void UpdateCursorPointerPosition()
        {

            Vector2 pos = _cursorController?.CursorPosition ?? new Vector2(0f, 0f);
            //Vector2 pointerSize = GetPointerSize();

            double xOffset = pos.X /*- pointerSize / 2*/;
            double yOffset = pos.Y /*- pointerSize / 2*/;

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
                await _cursorController.SetCursorPositionAsync(newPosition);
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
