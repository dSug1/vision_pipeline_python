using System.Diagnostics;
using System.Numerics;

namespace MauiApp_Launcher
{
    public partial class MainPage : ContentPage
    {
        private ICursorController _cursorController;                            //DEBUGGING: creates a cursor controller
        private HandTriggeredActions _handActions;

        public MainPage()
        {
            InitializeComponent();

            _cursorController = CreateCursorController();                       //DEBUGGING: create the cursor controller
            _handActions = new HandTriggeredActions(_cursorController, new XamlCursorUIUpdater(this));

        }

        //Cursor setup
        private ICursorController CreateCursorController()                      //DEBUGGING: method called to create the instantiation of the CursorController class
        {
            Vector2 pointerSize = new Vector2((float)CursorPointer.WidthRequest, (float)CursorPointer.HeightRequest);       //Set the size of the cursor in the xaml.cs page
            return new CursorController(pointerSize);
        }


        // Client setup
        /* WARNING: make sure the Python Server is already launched & is therefore listening */
        protected override async void OnAppearing()                             //create the Client connection when the page is loaded. The Server should already be listening
        {
            base.OnAppearing();

            var client = new Client("127.0.0.1", 5050, this);
            await client.ConnectAsync();
        }
        
        //Receive data from Client.cs
        public void ReceiveFloatArray(string type, float[] data)
        {
            // Handle the incoming float array
            //Debug.WriteLine($"[MainPage] Received {type} data with [{string.Join(", ", data)}]");
            switch (type)
            {
                case "face":
                    // TODO: Add logic for face movement
                    break;

                case "hands":
                    if (data[16] != 0 || data[17] !=0)   _handActions.LeftIndexTip(new Vector2(data[16], data[17]));               // Index finger tip = landmark 8 in MediaPipe)                   
                    break;

                default:
                    Debug.WriteLine($"[MainPage] Unknown type: {type}");
                    break;
            }

        }

        //Update the cursor in UI as per cursorpositioner

        public void UpdateCursorInUI()
        {

            Vector2 pos = _cursorController?.CursorTargetPosition ?? new Vector2(0f, 0f);
            //Vector2 pointerSize = GetPointerSize();

            double xOffset = pos.X; //*- pointerSize / 2
            double yOffset = pos.Y; //*- pointerSize / 2

            if (CursorPointer != null)
            {
                CursorPointer.TranslationX = xOffset;
                CursorPointer.TranslationY = yOffset;
            }
        }



        /*DEBUGGING*/


        /*NOT USED 
        DEBUGGING - change position of cursor based on sliders in the xaml page
        private async void CursorXPosition_ValueChanged(object sender, ValueChangedEventArgs e)
        {
            if (_cursorController != null)
            {
                var newPosition = new Vector2((float)e.NewValue, _cursorController.CursorPosition.Y);
                await _cursorController.SetCursorPositionAsync(newPosition);
                UpdateCursorPointerPositioninXAMLPage();
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
                UpdateCursorPointerPositioninXAMLPage();
            }
            // Update label to show current zoom level
            CursorYPositionLabel.Text = _cursorController != null
                ? $"YPosition of cursor: {_cursorController.CursorPosition.Y:F2}"
                : "Cursor controller not initialized.";
        }
        */
    }
}
