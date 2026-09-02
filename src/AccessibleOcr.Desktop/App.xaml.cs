using System.IO;
using System.Text;
using System.Windows;
using System.Windows.Threading;

namespace AccessibleOcr.Desktop;

public partial class App : System.Windows.Application
{
    public App()
    {
        DispatcherUnhandledException += OnDispatcherUnhandledException;
        AppDomain.CurrentDomain.UnhandledException += OnUnhandledException;
        TaskScheduler.UnobservedTaskException += OnUnobservedTaskException;
    }

    private static void OnDispatcherUnhandledException(object sender, DispatcherUnhandledExceptionEventArgs eventArgs)
    {
        WriteErrorLog("UI", eventArgs.Exception);
        MessageBox.Show(
            "화면을 처리하는 중 오류가 발생했습니다. 앱은 계속 실행됩니다.\n\n" +
            "같은 문제가 반복되면 로그 파일을 개발팀에 전달해 주세요.",
            "접근형 OCR 오류",
            MessageBoxButton.OK,
            MessageBoxImage.Error);
        eventArgs.Handled = true;
    }

    private static void OnUnhandledException(object? sender, UnhandledExceptionEventArgs eventArgs)
    {
        if (eventArgs.ExceptionObject is Exception exception)
        {
            WriteErrorLog("AppDomain", exception);
        }
    }

    private static void OnUnobservedTaskException(object? sender, UnobservedTaskExceptionEventArgs eventArgs)
    {
        WriteErrorLog("Task", eventArgs.Exception);
        eventArgs.SetObserved();
    }

    private static void WriteErrorLog(string source, Exception exception)
    {
        try
        {
            var logDirectory = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                "AccessibleOcr",
                "logs");
            Directory.CreateDirectory(logDirectory);
            var logPath = Path.Combine(logDirectory, "app-errors.log");
            var entry = new StringBuilder()
                .AppendLine($"[{DateTimeOffset.Now:O}] {source}")
                .AppendLine(exception.ToString())
                .AppendLine()
                .ToString();
            File.AppendAllText(logPath, entry, Encoding.UTF8);
        }
        catch
        {
            // 오류 기록 실패가 원래 예외 처리를 방해하지 않게 한다.
        }
    }
}
