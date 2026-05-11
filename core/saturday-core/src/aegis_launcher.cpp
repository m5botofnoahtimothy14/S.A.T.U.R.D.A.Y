#include <winsock2.h>
#include <ws2tcpip.h>
#include <windows.h>

#include <filesystem>
#include <fstream>
#include <iostream>
#include <optional>
#include <sstream>
#include <string>
#include <vector>

namespace fs = std::filesystem;

namespace {

struct WinsockSession {
    WinsockSession() : ok(WSAStartup(MAKEWORD(2, 2), &data) == 0) {}
    ~WinsockSession() {
        if (ok) {
            WSACleanup();
        }
    }

    bool ok{false};
    WSADATA data{};
};

std::wstring quote_arg(const std::wstring& arg) {
    if (arg.find_first_of(L" \t\"") == std::wstring::npos) {
        return arg;
    }
    std::wstring quoted = L"\"";
    for (wchar_t ch : arg) {
        if (ch == L'"') {
            quoted += L"\\\"";
        } else {
            quoted += ch;
        }
    }
    quoted += L"\"";
    return quoted;
}

std::wstring build_command_line(const fs::path& app, const std::vector<std::wstring>& args) {
    std::wstring cmd = quote_arg(app.wstring());
    for (const auto& arg : args) {
        cmd += L" ";
        cmd += quote_arg(arg);
    }
    return cmd;
}

bool create_process(
    const fs::path& app,
    const std::vector<std::wstring>& args,
    const fs::path& working_dir,
    bool wait_for_exit,
    bool hide_window,
    const std::optional<fs::path>& stdout_file,
    const std::optional<fs::path>& stderr_file,
    DWORD* out_pid
) {
    STARTUPINFOW startup{};
    startup.cb = sizeof(startup);
    PROCESS_INFORMATION process_info{};

    HANDLE h_stdout = nullptr;
    HANDLE h_stderr = nullptr;
    bool inherit_handles = false;

    if (stdout_file.has_value()) {
        h_stdout = CreateFileW(
            stdout_file->c_str(),
            FILE_APPEND_DATA,
            FILE_SHARE_READ | FILE_SHARE_WRITE,
            nullptr,
            OPEN_ALWAYS,
            FILE_ATTRIBUTE_NORMAL,
            nullptr
        );
        if (h_stdout == INVALID_HANDLE_VALUE) {
            std::wcerr << L"[WARN] Failed to open stdout log: " << stdout_file->wstring() << L"\n";
            h_stdout = nullptr;
        } else {
            SetFilePointer(h_stdout, 0, nullptr, FILE_END);
            SetHandleInformation(h_stdout, HANDLE_FLAG_INHERIT, HANDLE_FLAG_INHERIT);
            inherit_handles = true;
        }
    }

    if (stderr_file.has_value()) {
        h_stderr = CreateFileW(
            stderr_file->c_str(),
            FILE_APPEND_DATA,
            FILE_SHARE_READ | FILE_SHARE_WRITE,
            nullptr,
            OPEN_ALWAYS,
            FILE_ATTRIBUTE_NORMAL,
            nullptr
        );
        if (h_stderr == INVALID_HANDLE_VALUE) {
            std::wcerr << L"[WARN] Failed to open stderr log: " << stderr_file->wstring() << L"\n";
            h_stderr = nullptr;
        } else {
            SetFilePointer(h_stderr, 0, nullptr, FILE_END);
            SetHandleInformation(h_stderr, HANDLE_FLAG_INHERIT, HANDLE_FLAG_INHERIT);
            inherit_handles = true;
        }
    }

    if (inherit_handles) {
        startup.dwFlags |= STARTF_USESTDHANDLES;
        startup.hStdInput = GetStdHandle(STD_INPUT_HANDLE);
        startup.hStdOutput = h_stdout ? h_stdout : GetStdHandle(STD_OUTPUT_HANDLE);
        startup.hStdError = h_stderr ? h_stderr : GetStdHandle(STD_ERROR_HANDLE);
    }

    if (hide_window) {
        startup.dwFlags |= STARTF_USESHOWWINDOW;
        startup.wShowWindow = SW_HIDE;
    }

    const std::wstring command_line = build_command_line(app, args);
    std::vector<wchar_t> command_buffer(command_line.begin(), command_line.end());
    command_buffer.push_back(L'\0');

    DWORD creation_flags = CREATE_UNICODE_ENVIRONMENT;
    if (hide_window) {
        creation_flags |= CREATE_NO_WINDOW;
    }

    const BOOL started = CreateProcessW(
        app.c_str(),
        command_buffer.data(),
        nullptr,
        nullptr,
        inherit_handles ? TRUE : FALSE,
        creation_flags,
        nullptr,
        working_dir.c_str(),
        &startup,
        &process_info
    );

    if (h_stdout) {
        CloseHandle(h_stdout);
    }
    if (h_stderr) {
        CloseHandle(h_stderr);
    }

    if (!started) {
        const DWORD err = GetLastError();
        std::wcerr << L"[ERROR] Failed to start process: " << app.wstring() << L" (Win32 " << err << L")\n";
        return false;
    }

    if (out_pid) {
        *out_pid = process_info.dwProcessId;
    }

    if (wait_for_exit) {
        WaitForSingleObject(process_info.hProcess, INFINITE);
    }

    CloseHandle(process_info.hThread);
    CloseHandle(process_info.hProcess);
    return true;
}

bool write_pid_file(const fs::path& pid_file, DWORD pid) {
    std::ofstream out(pid_file, std::ios::trunc);
    if (!out.is_open()) {
        return false;
    }
    out << pid;
    return true;
}

std::optional<DWORD> read_pid_file(const fs::path& pid_file) {
    std::ifstream in(pid_file);
    if (!in.is_open()) {
        return std::nullopt;
    }
    DWORD pid = 0;
    in >> pid;
    if (pid == 0) {
        return std::nullopt;
    }
    return pid;
}

bool is_process_running(DWORD pid) {
    HANDLE handle = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, FALSE, pid);
    if (!handle) {
        return false;
    }
    DWORD exit_code = 0;
    const BOOL ok = GetExitCodeProcess(handle, &exit_code);
    CloseHandle(handle);
    return ok && exit_code == STILL_ACTIVE;
}

bool is_tcp_port_listening(unsigned short port) {
    WinsockSession winsock;
    if (!winsock.ok) {
        return false;
    }

    SOCKET sock = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
    if (sock == INVALID_SOCKET) {
        return false;
    }

    DWORD timeout_ms = 500;
    setsockopt(sock, SOL_SOCKET, SO_RCVTIMEO, reinterpret_cast<const char*>(&timeout_ms), sizeof(timeout_ms));
    setsockopt(sock, SOL_SOCKET, SO_SNDTIMEO, reinterpret_cast<const char*>(&timeout_ms), sizeof(timeout_ms));

    sockaddr_in addr{};
    addr.sin_family = AF_INET;
    addr.sin_port = htons(port);
    addr.sin_addr.s_addr = htonl(INADDR_LOOPBACK);

    const int rc = connect(sock, reinterpret_cast<sockaddr*>(&addr), sizeof(addr));
    closesocket(sock);
    return rc == 0;
}

std::wstring to_wide(const fs::path& path) {
    return path.wstring();
}

}  // namespace

int wmain() {
    wchar_t exe_path[MAX_PATH]{};
    const DWORD len = GetModuleFileNameW(nullptr, exe_path, MAX_PATH);
    if (len == 0 || len == MAX_PATH) {
        std::wcerr << L"[ERROR] Unable to resolve launcher path.\n";
        return 1;
    }

    const fs::path root = fs::path(exe_path).parent_path();
    const fs::path logs_dir = root / "logs";
    const fs::path run_dir = root / "run";

    std::error_code ec;
    fs::create_directories(logs_dir, ec);
    fs::create_directories(run_dir, ec);

    const fs::path visual_core = root / "aegis-core" / "bin" / "Release" / "aegis-core.exe";
    const fs::path broker_exe = root / "build" / "mosqdl" / "inst" / "mosquitto.exe";
    const fs::path broker_conf = root / "build" / "mosqdl" / "inst" / "mosq-open.conf";
    const fs::path python_exe = root / ".venv" / "Scripts" / "python.exe";
    const fs::path run_production_py = root / "run_production.py";

    const fs::path broker_pid_file = run_dir / "broker.pid";
    const fs::path backend_pid_file = run_dir / "backend.pid";

    std::wcout << L"========================================\n";
    std::wcout << L"  AEGIS ORCHESTRATOR INITIALIZING\n";
    std::wcout << L"========================================\n";

    if (fs::exists(visual_core)) {
        std::wcout << L"[1/3] Launching visual core...\n";
        create_process(
            visual_core,
            {},
            visual_core.parent_path(),
            true,
            true,
            std::nullopt,
            std::nullopt,
            nullptr
        );
    } else {
        std::wcout << L"[1/3] Visual core not found, continuing.\n";
    }

    std::wcout << L"[2/3] Ensuring MQTT broker...\n";
    if (fs::exists(broker_exe)) {
        if (is_tcp_port_listening(1884)) {
            std::wcout << L"      Mosquitto already listening on 127.0.0.1:1884.\n";
        } else {
            DWORD broker_pid = 0;
            const bool broker_started = create_process(
                broker_exe,
                {L"-c", to_wide(broker_conf), L"-v"},
                broker_exe.parent_path(),
                false,
                true,
                logs_dir / "mosquitto.out",
                logs_dir / "mosquitto.err",
                &broker_pid
            );
            if (broker_started) {
                write_pid_file(broker_pid_file, broker_pid);
                std::wcout << L"      Mosquitto started (PID " << broker_pid << L").\n";
            } else {
                std::wcerr << L"      Failed to start Mosquitto.\n";
            }
        }
    } else {
        std::wcout << L"      Mosquitto binary missing, skipping broker startup.\n";
    }

    std::wcout << L"[3/3] Ensuring AEGIS backend...\n";
    bool backend_running = false;
    if (auto pid = read_pid_file(backend_pid_file); pid.has_value()) {
        if (is_process_running(*pid)) {
            backend_running = true;
            std::wcout << L"      Backend already running (PID " << *pid << L").\n";
        } else {
            std::error_code remove_ec;
            fs::remove(backend_pid_file, remove_ec);
        }
    }

    if (!backend_running) {
        if (!fs::exists(python_exe)) {
            std::wcerr << L"      Python runtime not found at " << python_exe.wstring() << L"\n";
            return 2;
        }
        if (!fs::exists(run_production_py)) {
            std::wcerr << L"      run_production.py not found at " << run_production_py.wstring() << L"\n";
            return 3;
        }

        DWORD backend_pid = 0;
        const bool backend_started = create_process(
            python_exe,
            {L"run_production.py", L"--mode", L"server"},
            root,
            false,
            true,
            logs_dir / "backend.out",
            logs_dir / "backend.err",
            &backend_pid
        );

        if (!backend_started) {
            std::wcerr << L"      Failed to start AEGIS backend.\n";
            return 4;
        }

        write_pid_file(backend_pid_file, backend_pid);
        std::wcout << L"      AEGIS backend started (PID " << backend_pid << L").\n";
    }

    std::wcout << L"Startup orchestration complete.\n";
    std::wcout << L"Logs directory: " << logs_dir.wstring() << L"\n";
    return 0;
}
