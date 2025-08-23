using System;
using System.Diagnostics;
using System.IO;
using System.Threading.Tasks;

namespace MauiApp_Launcher
{
    public class Launcher
    {
        private readonly string _host;
        private readonly int _port;

        public Launcher(string host, int port)
        {
            _host = host;
            _port = port;
        }

        public Task LaunchPythonServerAsync()
        {
            try
            {
                // Resolve path to Main.py relative to the app's base directory
                string baseDir = AppContext.BaseDirectory;
                string parentDir = Directory.GetParent(Directory.GetParent(baseDir).FullName).FullName;
                string mainPath = Path.Combine(parentDir, "Python_Server_MediaPipe_vision_pipeline", "Main.py");

                string pythonExe = "python"; // Or full path to python.exe if needed

                var startInfo = new ProcessStartInfo
                {
                    FileName = pythonExe,
                    Arguments = $"\"{mainPath}\" --host {_host} --port {_port}",
                    UseShellExecute = false,
                    CreateNoWindow = true
                };

                Process.Start(startInfo);
                Debug.WriteLine($"[Launcher] Started Main.py on {_host}:{_port}");
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"[Launcher] Error launching Main.py: {ex.Message}");
            }

            return Task.CompletedTask;
        }
    }
}
