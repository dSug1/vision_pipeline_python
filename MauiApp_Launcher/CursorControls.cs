using System.Numerics;


namespace MauiApp_Launcher
{
    public interface ICursorController
    {
        Vector2 CursorTargetPosition { get; }
        Task SetCursorTargetPositionAsync(Vector2 position);
    }

        public interface ICursorUIUpdater
    {
        void UpdateCursorPositioninUI();
    }



    public class CursorController : ICursorController, IDisposable
    {
        private  float _screenWidth;
        private  float _screenHeight;
        private readonly Vector2 _pointerSize;
        private bool _disposed;

        public CursorController(Vector2 pointerSize)
        {
            _pointerSize = pointerSize;
            UpdateScreenDimensions(DeviceDisplay.MainDisplayInfo);
            DeviceDisplay.MainDisplayInfoChanged += OnMainDisplayInfoChanged;
        }

        public Vector2 CursorTargetPosition { get; private set; } = new(0f, 0f);

        public Task SetCursorTargetPositionAsync(Vector2 position)
        {
            float clampedX = Math.Clamp(position.X, 0f, _screenWidth - _pointerSize.X);
            float clampedY = Math.Clamp(position.Y, 0f, _screenHeight - _pointerSize.Y);
            CursorTargetPosition = new Vector2(clampedX, clampedY);
            return Task.CompletedTask;
        }

        private void OnMainDisplayInfoChanged(object? sender, DisplayInfoChangedEventArgs e)
        {
            UpdateScreenDimensions(e.DisplayInfo);
        }

        private void UpdateScreenDimensions(DisplayInfo info)
        {
            _screenWidth = (float)(info.Width /*/ info.Density*/);          //DeviceDisplay.MainDisplayInfo gives the screen size in pixels, so dividing by Density converts it to device-independent units (DIPs),
            _screenHeight = (float)(info.Height /*/ info.Density*/);
        }
        public void Dispose()
        {
            if (_disposed) return;
            DeviceDisplay.MainDisplayInfoChanged -= OnMainDisplayInfoChanged;
            _disposed = true;
        }
    }
    public class XamlCursorUIUpdater : ICursorUIUpdater
    {
        private readonly MainPage _page;

        public XamlCursorUIUpdater(MainPage page)
        {
            _page = page;
        }

        public void UpdateCursorPositioninUI()
        {
            _page.UpdateCursorInUI();
        }
    }
}
