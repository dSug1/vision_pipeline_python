using System.Numerics;
using System.Threading.Tasks;

namespace MauiApp_Launcher
{
    public class HandTriggeredActions
    {
        private readonly ICursorController _cursorSetter;
        private readonly ICursorUIUpdater _uiUpdater;

        public HandTriggeredActions(ICursorController cursorController, ICursorUIUpdater uiUpdater)
        {
            _cursorSetter = cursorController;
            _uiUpdater = uiUpdater;
        }

        public void LeftIndexTip(Vector2 position)
        {
            _cursorSetter.SetCursorTargetPositionAsync(position);
            _uiUpdater.UpdateCursorPositioninUI();
        }
    }

}
