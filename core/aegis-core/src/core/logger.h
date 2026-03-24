#pragma once

#include <string>
#include <memory>
#include <mutex>
#include <fstream>
#include <sstream>
#include <iostream>
#include <chrono>
#include <cstring>

namespace aegis {

/**
 * @enum LogLevel
 * @brief Severity levels for logging system
 */
enum class LogLevel : uint8_t {
    Debug = 0,
    Info,
    Warning,
    Error,
    Critical
};

/**
 * @class Logger
 * @brief Thread-safe singleton logger with file and console output
 * 
 * Provides centralized logging with timestamps, severity levels,
 * and both file and console output streams. Uses RAII for resource management.
 */
class Logger {
public:
    // Delete copy/move for singleton
    Logger(const Logger&) = delete;
    Logger& operator=(const Logger&) = delete;
    Logger(Logger&&) = delete;
    Logger& operator=(Logger&&) = delete;

    /**
     * @brief Get singleton instance
     */
    static Logger& instance() {
        static Logger instance;
        return instance;
    }

    /**
     * @brief Initialize logger with output configuration
     * @param log_file Path to log file (empty for console-only)
     * @param min_level Minimum log level to output
     */
    void initialize(const std::string& log_file = "", LogLevel min_level = LogLevel::Info) {
        std::lock_guard<std::mutex> lock(mutex_);
        min_level_ = min_level;
        
        if (!log_file.empty()) {
            log_file_.open(log_file, std::ios::app);
            file_output_ = log_file_.is_open();
        }
    }

    /**
     * @brief Log a message with specified level
     */
    void log(LogLevel level, const std::string& component, const std::string& message) {
        if (level < min_level_) return;

        std::lock_guard<std::mutex> lock(mutex_);
        
        auto now = std::chrono::system_clock::now();
        auto time_t = std::chrono::system_clock::to_time_t(now);
        auto ms = std::chrono::duration_cast<std::chrono::milliseconds>(
            now.time_since_epoch()) % 1000;

        std::tm tm_buf;
#ifdef _WIN32
        localtime_s(&tm_buf, &time_t);
#else
        localtime_r(&time_t, &tm_buf);
#endif

        char timestamp[32];
        std::strftime(timestamp, sizeof(timestamp), "%Y-%m-%d %H:%M:%S", &tm_buf);
        
        std::ostringstream oss;
        oss << "[" << timestamp << "." << std::setfill('0') << std::setw(3) << ms.count() << "] "
            << "[" << level_string(level) << "] "
            << "[" << component << "] " << message;

        std::string log_line = oss.str();
        
        // Console output
        std::cout << log_line << std::endl;
        
        // File output
        if (file_output_ && log_file_.is_open()) {
            log_file_ << log_line << std::endl;
            log_file_.flush();
        }
    }

    // Convenience methods
    void debug(const std::string& component, const std::string& msg) { 
        log(LogLevel::Debug, component, msg); 
    }
    void info(const std::string& component, const std::string& msg) { 
        log(LogLevel::Info, component, msg); 
    }
    void warning(const std::string& component, const std::string& msg) { 
        log(LogLevel::Warning, component, msg); 
    }
    void error(const std::string& component, const std::string& msg) { 
        log(LogLevel::Error, component, msg); 
    }
    void critical(const std::string& component, const std::string& msg) { 
        log(LogLevel::Critical, component, msg); 
    }

private:
    Logger() = default;
    ~Logger() {
        if (log_file_.is_open()) {
            log_file_.flush();
            log_file_.close();
        }
    }

    static std::string level_string(LogLevel level) {
        switch (level) {
            case LogLevel::Debug:    return "DEBUG";
            case LogLevel::Info:     return "INFO";
            case LogLevel::Warning:  return "WARN";
            case LogLevel::Error:    return "ERROR";
            case LogLevel::Critical: return "CRIT";
            default: return "UNKNOWN";
        }
    }

    std::mutex mutex_;
    std::ofstream log_file_;
    bool file_output_ = false;
    LogLevel min_level_ = LogLevel::Info;
};

// Convenience macro
#define AEGIS_LOG(level, component, msg) \
    aegis::Logger::instance().log(aegis::LogLevel::level, component, msg)

#define AEGIS_DEBUG(component, msg) AEGIS_LOG(Debug, component, msg)
#define AEGIS_INFO(component, msg) AEGIS_LOG(Info, component, msg)
#define AEGIS_WARN(component, msg) AEGIS_LOG(Warning, component, msg)
#define AEGIS_ERROR(component, msg) AEGIS_LOG(Error, component, msg)
#define AEGIS_CRITICAL(component, msg) AEGIS_LOG(Critical, component, msg)

} // namespace aegis
