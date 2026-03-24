#pragma once

#include <chrono>
#include <string>
#include <vector>

namespace aegis {

/**
 * @class Timer
 * @brief High-resolution timer for performance measurement
 */
class Timer {
public:
    using Clock = std::chrono::high_resolution_clock;
    using TimePoint = Clock::time_point;
    using Duration = std::chrono::duration<double, std::milli>;

    Timer() : start_(Clock::now()) {}

    /**
     * @brief Reset timer to current time
     */
    void reset() { start_ = Clock::now(); }

    /**
     * @brief Get elapsed time in seconds
     */
    double elapsed_seconds() const {
        return std::chrono::duration<double>(Clock::now() - start_).count();
    }

    /**
     * @brief Get elapsed time in milliseconds
     */
    double elapsed_milliseconds() const {
        return Duration(Clock::now() - start_).count();
    }

    /**
     * @brief Get elapsed time in microseconds
     */
    double elapsed_microseconds() const {
        return std::chrono::duration<double, std::micro>(Clock::now() - start_).count();
    }

    /**
     * @brief Get elapsed time as a formatted string
     */
    std::string elapsed_string() const {
        double ms = elapsed_milliseconds();
        if (ms < 1.0) {
            return std::to_string(elapsed_microseconds()) + "μs";
        } else if (ms < 1000.0) {
            return std::to_string(ms) + "ms";
        } else {
            return std::to_string(ms / 1000.0) + "s";
        }
    }

private:
    TimePoint start_;
};

/**
 * @class FrameRateCounter
 * @brief Tracks frame rate over a sliding window
 */
class FrameRateCounter {
public:
    FrameRateCounter(size_t window_size = 60) 
        : window_size_(window_size), frame_times_(window_size), index_(0), count_(0) {}

    /**
     * @brief Record a frame time
     */
    void record_frame(double frame_time_ms) {
        frame_times_[index_] = frame_time_ms;
        index_ = (index_ + 1) % window_size_;
        if (count_ < window_size_) ++count_;
    }

    /**
     * @brief Get current FPS
     */
    double fps() const {
        if (count_ == 0) return 0.0;
        double total = 0.0;
        for (size_t i = 0; i < count_; ++i) {
            total += frame_times_[i];
        }
        if (total <= 0.0) return 0.0;
        return (count_ * 1000.0) / total;
    }

    /**
     * @brief Get average frame time in milliseconds
     */
    double average_frame_time() const {
        if (count_ == 0) return 0.0;
        double total = 0.0;
        for (size_t i = 0; i < count_; ++i) {
            total += frame_times_[i];
        }
        return total / count_;
    }

    /**
     * @brief Get minimum frame time
     */
    double min_frame_time() const {
        if (count_ == 0) return 0.0;
        double min_time = frame_times_[0];
        for (size_t i = 1; i < count_; ++i) {
            if (frame_times_[i] < min_time) min_time = frame_times_[i];
        }
        return min_time;
    }

    /**
     * @brief Get maximum frame time
     */
    double max_frame_time() const {
        if (count_ == 0) return 0.0;
        double max_time = frame_times_[0];
        for (size_t i = 1; i < count_; ++i) {
            if (frame_times_[i] > max_time) max_time = frame_times_[i];
        }
        return max_time;
    }

private:
    size_t window_size_;
    std::vector<double> frame_times_;
    size_t index_;
    size_t count_;
};

/**
 * @class ScopedTimer
 * @brief RAII timer that logs on destruction
 */
class ScopedTimer {
public:
    ScopedTimer(const std::string& name, bool log = true) 
        : name_(name), log_(log), timer_() {}
    
    ~ScopedTimer() {
        if (log_) {
            AEGIS_INFO("Timer", name_ + ": " + timer_.elapsed_string());
        }
    }

    double elapsed_ms() const { return timer_.elapsed_milliseconds(); }

private:
    std::string name_;
    bool log_;
    Timer timer_;
};

} // namespace aegis
