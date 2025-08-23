using System;
using System.IO;
using System.Net.Sockets;
using System.Numerics;
using System.Text;
using System.Text.Json;
using System.Threading.Tasks;

namespace MauiApp_Launcher
{
    public class Client
    {
        private readonly string _host;
        private readonly int _port;
        private TcpClient _tcpClient;
        private NetworkStream _stream;
        private readonly string _outputDir;

        public Client(string host = "127.0.0.1", int port = 5050)
        {
            _host = host;
            _port = port;
            _outputDir = Path.Combine(FileSystem.AppDataDirectory, "ReceivedDataJsonFiles");
            Directory.CreateDirectory(_outputDir);
        }

        public async Task ConnectAsync()
        {
            try
            {
                _tcpClient = new TcpClient();
                await _tcpClient.ConnectAsync(_host, _port);
                _stream = _tcpClient.GetStream();
                Console.WriteLine($"[Client] Connected to {_host}:{_port}");

                await ReceiveKeypointsDataAsync();
            }
            catch (Exception ex)
            {
                Console.WriteLine($"[Client] Connection error: {ex.Message}");
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
                        Console.WriteLine("[Client] Connection closed by server.");
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
                        }
                        catch (JsonException je)
                        {
                            Console.WriteLine($"[Client] JSON decode error: {je.Message}");
                        }
                        catch (Exception e)
                        {
                            Console.WriteLine($"[Client] Error processing packet: {e.Message}");
                        }
                    }
                }
            }
            catch (Exception e)
            {
                Console.WriteLine($"[Client] Stream error: {e.Message}");
            }
            finally
            {
                _stream?.Close();
                _tcpClient?.Close();
                Console.WriteLine("[Client] Socket closed.");
            }
        }
    }
}
