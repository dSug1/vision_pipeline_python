using System.Numerics;
using System.Threading.Tasks;

namespace MauiApp_Launcher
{
    public interface ICursorController
    {
        Vector2 CursorPosition { get; }
        Task SetCursorPositionAsync(Vector2 position);
    }

    public class CursorController : ICursorController
    {
        private readonly float _imageWidth = 300f;
        private readonly float _imageHeight = 200f;
        private readonly Vector2 _pointerSize;

        public CursorController(Vector2 pointerSize)
        {
            _pointerSize = pointerSize;
        }

        public Vector2 CursorPosition { get; private set; } = new(0f, 0f);

        public Task SetCursorPositionAsync(Vector2 position)
        {
            float clampedX = Math.Clamp(position.X, 0f, _imageWidth - _pointerSize.X);
            float clampedY = Math.Clamp(position.Y, 0f, _imageHeight - _pointerSize.Y);
            CursorPosition = new Vector2(clampedX, clampedY);
            return Task.CompletedTask;
        }
    }
}
