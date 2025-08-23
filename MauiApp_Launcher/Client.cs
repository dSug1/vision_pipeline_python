using System;
using System.IO;
using System.Net.Sockets;
using System.Numerics;
using System.Text;
using System.Text.Json;
using System.Threading.Tasks;
using System.Diagnostics;


namespace MauiApp_Launcher
{
    public class Client
    {
        private readonly string _host;
        private readonly int _port;
        private TcpClient _tcpClient = null;
        private NetworkStream _stream = null;
        private readonly string _outputDir = string.Empty;
        private readonly MainPage _mainPage;

        public Client(string host, int port, MainPage mainPage)
        {
            _host = host;
            _port = port;
            _mainPage = mainPage;
            /*NOT USED alternative location where received JSON files will be saved in FileSystem.AppDataDirectory, which is cross-platform safe
            _outputDir = Path.Combine(FileSystem.AppDataDirectory, "ReceivedDataJsonFiles");
            */
            _outputDir = Path.Combine(AppContext.BaseDirectory, "ReceivedDataJsonFiles");
            Directory.CreateDirectory(_outputDir);
        }

        public async Task ConnectAsync()
        {
            try
            {
                _tcpClient = new TcpClient();
                await _tcpClient.ConnectAsync(_host, _port);
                _stream = _tcpClient.GetStream();
                Debug.WriteLine($"[Client] Connected to {_host}:{_port}");

                await ReceiveKeypointsDataAsync();
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"[Client] Connection error: {ex.Message}");
            }
        }

        private async Task ReceiveKeypointsDataAsync()
        {
            var buffer = new byte[4096];
            var stringBuffer = new StringBuilder();

            try
            {
                while (_tcpClient.Connected)
                {
                    int bytesRead = await _stream.ReadAsync(buffer, 0, buffer.Length);
                    if (bytesRead == 0)
                    {
                        Debug.WriteLine("[Client] Connection closed by server.");
                        break;
                    }

                    string chunk = Encoding.UTF8.GetString(buffer, 0, bytesRead);
                    stringBuffer.Append(chunk);

                    while (stringBuffer.ToString().Contains('\n'))
                    {
                        var fullBuffer = stringBuffer.ToString();
                        int newlineIndex = fullBuffer.IndexOf('\n');
                        string packet = fullBuffer.Substring(0, newlineIndex);
                        stringBuffer.Remove(0, newlineIndex + 1);

                        try
                        {
                            using var doc = JsonDocument.Parse(packet);
                            var root = doc.RootElement;

                            string type = root.GetProperty("type").GetString() ?? "unknown";
                            var data = root.GetProperty("data");

                            string outputPath = Path.Combine(_outputDir, $"received_{type}_data.json");
                            await File.WriteAllTextAsync(outputPath, JsonSerializer.Serialize(data, new JsonSerializerOptions { WriteIndented = true }));

                            // Read the just-written JSON file
                            string jsonContent = await File.ReadAllTextAsync(outputPath);

                            // Deserialize into a float array
                            float[]? floatArray = JsonSerializer.Deserialize<float[]>(jsonContent);

                            // Send to another script or handler
                            if (floatArray != null && floatArray.Length > 0)
                            {
                                await SendDataArrayToMainPageAsync(type, floatArray);
                            }
                            else
                            {
                                Debug.WriteLine($"[Client] Warning: Received null or empty float array for type '{type}'. Skipping MainPage dispatch.");
                            }

                        }
                        catch (JsonException je)
                        {
                            Debug.WriteLine($"[Client] JSON decode error: {je.Message}");
                        }
                        catch (Exception e)
                        {
                            Debug.WriteLine($"[Client] Error processing packet: {e.Message}");
                        }
                    }
                }
            }
            catch (Exception e)
            {
                Debug.WriteLine($"[Client] Stream error: {e.Message}");
            }
            finally
            {
                _stream?.Close();
                _tcpClient?.Close();
                Debug.WriteLine("[Client] Socket closed.");
            }
        }

        private async Task SendDataArrayToMainPageAsync(string type, float[] dataArray)
        {
            _mainPage.ReceiveFloatArray(type, dataArray);
            //Debug.WriteLine($"[Client] Sent {type} float array to MainPage.");
            await Task.CompletedTask; // placeholder to satisfy compiler
        }



    }
}
