#pragma once

#include <string>
#include <vector>
#include <functional>
#include <atomic>
#include <mutex>
#include <array>

namespace aegis {

enum class AudioState {
    Stopped,
    Playing,
    Paused,
    Recording
};

struct AudioFrame {
    std::vector<float> samples;
    int sample_rate;
    int channels;
    size_t frame_index;
};

class AudioEngine {
public:
    AudioEngine();
    ~AudioEngine();
    
    bool initialize(int sample_rate = 44100, int buffer_size = 1024);
    
    void shutdown();
    
    bool start_capture();
    
    void stop_capture();
    
    bool is_capturing() const { return capturing_.load(); }
    
    float get_audio_level() const;
    
    float get_audio_level_db() const;
    
    const std::vector<float>& get_samples() const { return sample_buffer_; }
    
    int get_sample_rate() const { return sample_rate_; }
    
    using AudioCallback = std::function<void(const AudioFrame&)>;
    void set_callback(AudioCallback callback);
    
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
    
    static constexpr size_t kLevelHistorySize = 64;
    float smoothed_level_ = 0.0f;
};

class FFTProcessor {
public:
    FFTProcessor();
    ~FFTProcessor();
    
    bool initialize(size_t size = 1024);
    
    void shutdown();
    
    void process(const float* samples, size_t count);
    
    const std::vector<float>& get_magnitudes() const { return magnitudes_; }
    
    const std::vector<float>& get_frequencies() const { return frequencies_; }
    
    const std::vector<float>& get_smoothed_magnitudes() const { return smoothed_magnitudes_; }
    
    float get_bass_energy() const;
    
    float get_mid_energy() const;
    
    float get_treble_energy() const;
    
    float get_total_energy() const;
    
    void set_smoothing(float factor) { smoothing_factor_ = factor; }
    
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
    
    void fft_real(std::vector<float>& real, std::vector<float>& imag);
};

struct AudioReactiveData {
    float bass = 0.0f;      // 0-1 normalized bass energy
    float mid = 0.0f;        // 0-1 normalized mid energy  
    float treble = 0.0f;     // 0-1 normalized treble energy
    float overall = 0.0f;    // 0-1 normalized overall energy
    float peak = 0.0f;       // 0-1 peak level
    
    float bass_smooth = 0.0f;
    float mid_smooth = 0.0f;
    float treble_smooth = 0.0f;
    float overall_smooth = 0.0f;
    
    std::array<float, 8> bands = {0};
    
    double timestamp = 0.0;
};

} // namespace aegis
