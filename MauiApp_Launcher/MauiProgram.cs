using Microsoft.Extensions.Logging;
using Microsoft.Maui.LifecycleEvents;
#if WINDOWS
using Microsoft.UI;
using Microsoft.UI.Windowing;
#endif

namespace MauiApp_Launcher
{
    public static class MauiProgram
    {
        public static MauiApp CreateMauiApp()
        {
            var builder = MauiApp.CreateBuilder();
            builder
                .UseMauiApp<App>()
                .ConfigureFonts(fonts =>
                {
                    fonts.AddFont("OpenSans-Regular.ttf", "OpenSansRegular");
                    fonts.AddFont("OpenSans-Semibold.ttf", "OpenSansSemibold");
                });

            // Add custom lifecycle configuration here so that the display occupies the full screen
            builder.ConfigureLifecycleEvents(events =>
            {
#if WINDOWS
                events.AddWindows(w =>
                {
                    w.OnWindowCreated(window =>
                    {
                        window.ExtendsContentIntoTitleBar = true;
                        IntPtr hWnd = WinRT.Interop.WindowNative.GetWindowHandle(window);
                        WindowId myWndId = Win32Interop.GetWindowIdFromWindow(hWnd);
                        var _appWindow = AppWindow.GetFromWindowId(myWndId);
                        _appWindow.SetPresenter(AppWindowPresenterKind.FullScreen);
                    });
                });
#endif
            });

#if DEBUG
            builder.Logging.AddDebug();
#endif

            return builder.Build();
        }
    }
}
