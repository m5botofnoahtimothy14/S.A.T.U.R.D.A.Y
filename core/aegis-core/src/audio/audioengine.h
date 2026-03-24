#pragma once

#include <string>
#include <vector>
#include <functional>
#include <atomic>
#include <mutex>
#include <array>

namespace aegis {

/**
 * @enum AudioState
 * @brief Audio system states
 */
enum class AudioState {
    Stopped,
    Playing,
    Paused,
    Recording
};

/**
 * @struct AudioFrame
 * @brief Audio sample data
 */
struct AudioFrame {
    std::vector<float> samples;
    int sample_rate;
    int channels;
    size_t frame_index;
};

/**
 * @class AudioEngine
 * @brief Cross-platform audio capture with real-time processing
 */
class AudioEngine {
public:
    AudioEngine();
    ~AudioEngine();
    
    /**
     * @brief Initialize audio subsystem
     * @param sample_rate Target sample rate (default 44100)
     * @param buffer_size Samples per buffer (default 1024)
     * @return true if successful
     */
    bool initialize(int sample_rate = 44100, int buffer_size = 1024);
    
    /**
     * @brief Shutdown audio subsystem
     */
    void shutdown();
    
    /**
     * @brief Start capturing audio
     */
    bool start_capture();
    
    /**
     * @brief Stop capturing audio
     */
    void stop_capture();
    
    /**
     * @brief Check if capturing
     */
    bool is_capturing() const { return capturing_.load(); }
    
    /**
     * @brief Get current audio level (RMS amplitude)
     */
    float get_audio_level() const;
    
    /**
     * @brief Get current audio level in decibels
     */
    float get_audio_level_db() const;
    
    /**
     * @brief Get raw sample buffer
     */
    const std::vector<float>& get_samples() const { return sample_buffer_; }
    
    /**
     * @brief Get sample rate
     */
    int get_sample_rate() const { return sample_rate_; }
    
    /**
     * @brief Set callback for audio data
     */
    using AudioCallback = std::function<void(const AudioFrame&)>;
    void set_callback(AudioCallback callback);
    
    /**
     * @brief Get current state
     */
    AudioState get_state() const { return state_.load(); }
    
private:
    void process_audio(const float* samples, size_t count);
    
    int sample_rate_ = 44100;
    int buffer_size_ = 1024;
    
    std::atomic<bool> capturing_{false};
    std::atomic<AudioState> state_{AudioState::Stopped};
    
    std::vector<float> sample_buffer_;
    std::vector<float> level_history_;
    
    float current_level_ = 0.0f;
    float peak_level_ = 0.0f;
    
    AudioCallback callback_;
    mutable std::mutex mutex_;
    
    // Smoothing
    static constexpr size_t kLevelHistorySize = 64;
    float smoothed_level_ = 0.0f;
};

/**
 * @class FFTProcessor
 * @brief Real-time FFT analysis for audio visualization
 */
class FFTProcessor {
public:
    FFTProcessor();
    ~FFTProcessor();
    
    /**
     * @brief Initialize FFT processor
     * @param size FFT window size (power of 2)
     * @return true if successful
     */
    bool initialize(size_t size = 1024);
    
    /**
     * @brief Shutdown FFT processor
     */
    void shutdown();
    
    /**
     * @brief Process audio samples and compute FFT
     * @param samples Input audio samples
     * @param count Number of samples
     */
    void process(const float* samples, size_t count);
    
    /**
     * @brief Get magnitude spectrum (normalized 0-1)
     */
    const std::vector<float>& get_magnitudes() const { return magnitudes_; }
    
    /**
     * @brief Get frequency bins
     */
    const std::vector<float>& get_frequencies() const { return frequencies_; }
    
    /**
     * @brief Get smoothed magnitudes for visualization
     */
    const std::vector<float>& get_smoothed_magnitudes() const { return smoothed_magnitudes_; }
    
    /**
     * @brief Get bass energy (20-250 Hz)
     */
    float get_bass_energy() const;
    
    /**
     * @brief Get mid energy (250-4000 Hz)
     */
    float get_mid_energy() const;
    
    /**
     * @brief Get treble energy (4000-20000 Hz)
     */
    float get_treble_energy() const;
    
    /**
     * @brief Get overall audio energy
     */
    float get_total_energy() const;
    
    /**
     * @brief Set smoothing factor (0-1)
     */
    void set_smoothing(float factor) { smoothing_factor_ = factor; }
    
    /**
     * @brief Get FFT size
     */
    size_t get_size() const { return fft_size_; }
    
private:
    void compute_fft();
    void apply_hann_window();
    
    size_t fft_size_ = 1024;
    std::vector<float> window_;
    std::vector<float> input_;
    std::vector<float> real_;
    std::vector<float> imag_;
    std::vector<float> magnitudes_;
    std::vector<float> frequencies_;
    std::vector<float> smoothed_magnitudes_;
    std::vector<float> prev_magnitudes_;
    
    float smoothing_factor_ = 0.3f;
    
    bool initialized_ = false;
    
    // FFT implementation (simplified - would use FFTW in production)
    void fft_real(std::vector<float>& real, std::vector<float>& imag);
};

/**
 * @class AudioReactiveData
 * @brief Processed audio data ready for visualization
 */
struct AudioReactiveData {
    float bass = 0.0f;      // 0-1 normalized bass energy
    float mid = 0.0f;        // 0-1 normalized mid energy  
    float treble = 0.0f;     // 0-1 normalized treble energy
    float overall = 0.0f;    // 0-1 normalized overall energy
    float peak = 0.0f;       // 0-1 peak level
    
    // Smoothed values for visualization
    float bass_smooth = 0.0f;
    float mid_smooth = 0.0f;
    float treble_smooth = 0.0f;
    float overall_smooth = 0.0f;
    
    // Frequency bands (8 bands)
    std::array<float, 8> bands = {0};
    
    // Timestamp
    double timestamp = 0.0;
};

} // namespace aegis
