#include "audio/audioengine.h"

namespace aegis {

AudioEngine::AudioEngine() = default;
AudioEngine::~AudioEngine() = default;

bool AudioEngine::initialize(int sample_rate, int buffer_size) {
    sample_rate_ = sample_rate;
    buffer_size_ = buffer_size;
    return true;
}

void AudioEngine::shutdown() {
    stop_capture();
}

bool AudioEngine::start_capture() {
    capturing_ = true;
    state_ = AudioState::Recording;
    return true;
}

void AudioEngine::stop_capture() {
    capturing_ = false;
    state_ = AudioState::Stopped;
}

float AudioEngine::get_audio_level() const {
    std::lock_guard<std::mutex> lock(mutex_);
    return current_level_;
}

float AudioEngine::get_audio_level_db() const {
    float level = get_audio_level();
    if (level <= 0.0f) return -120.0f;
    return 20.0f * std::log10(level);
}

void AudioEngine::set_callback(AudioCallback callback) {
    callback_ = callback;
}

void AudioEngine::process_audio(const float* samples, size_t count) {
    float sum = 0.0f;
    for (size_t i = 0; i < count; ++i) {
        sum += samples[i] * samples[i];
    }
    float rms = std::sqrt(sum / count);
    
    {
        std::lock_guard<std::mutex> lock(mutex_);
        current_level_ = rms;
    }
    
    if (callback_) {
        AudioFrame frame;
        frame.samples.assign(samples, samples + count);
        frame.sample_rate = sample_rate_;
        frame.channels = 1;
        callback_(frame);
    }
}

FFTProcessor::FFTProcessor() = default;
FFTProcessor::~FFTProcessor() = default;

bool FFTProcessor::initialize(size_t size) {
    fft_size_ = size;
    
    window_.resize(fft_size_);
    input_.resize(fft_size_);
    real_.resize(fft_size_ / 2 + 1);
    imag_.resize(fft_size_ / 2 + 1);
    magnitudes_.resize(fft_size_ / 2 + 1);
    frequencies_.resize(fft_size_ / 2 + 1);
    smoothed_magnitudes_.resize(fft_size_ / 2 + 1);
    prev_magnitudes_.resize(fft_size_ / 2 + 1);
    
    // Create Hann window
    for (size_t i = 0; i < fft_size_; ++i) {
        window_[i] = 0.5f * (1.0f - std::cos(2.0f * 3.14159f * i / (fft_size_ - 1)));
    }
    
    // Calculate frequency bins
    float sample_rate = 44100.0f;
    for (size_t i = 0; i < frequencies_.size(); ++i) {
        frequencies_[i] = (float)i * sample_rate / fft_size_;
    }
    
    initialized_ = true;
    return true;
}

void FFTProcessor::shutdown() {
    initialized_ = false;
}

void FFTProcessor::process(const float* samples, size_t count) {
    if (!initialized_ || count < fft_size_) return;
    
    // Apply window
    for (size_t i = 0; i < fft_size_; ++i) {
        input_[i] = samples[i] * window_[i];
    }
    
    compute_fft();
    
    // Calculate magnitudes
    for (size_t i = 0; i < magnitudes_.size(); ++i) {
        magnitudes_[i] = std::sqrt(real_[i] * real_[i] + imag_[i] * imag_[i]);
        
        // Normalize
        magnitudes_[i] /= fft_size_;
        
        // Apply smoothing
        smoothed_magnitudes_[i] = smoothing_factor_ * magnitudes_[i] + 
                                  (1.0f - smoothing_factor_) * prev_magnitudes_[i];
        prev_magnitudes_[i] = smoothed_magnitudes_[i];
    }
}

void FFTProcessor::compute_fft() {
    // Simplified FFT (would use FFTW in production)
    // For now, just copy input as placeholder
    for (size_t i = 0; i < real_.size(); ++i) {
        real_[i] = i < input_.size() ? input_[i] : 0.0f;
        imag_[i] = 0.0f;
    }
}

float FFTProcessor::get_bass_energy() const {
    size_t bass_end = static_cast<size_t>(250.0f * fft_size_ / 44100.0f);
    float energy = 0.0f;
    for (size_t i = 0; i < bass_end && i < smoothed_magnitudes_.size(); ++i) {
        energy += smoothed_magnitudes_[i];
    }
    return std::min(energy / bass_end * 10.0f, 1.0f);
}

float FFTProcessor::get_mid_energy() const {
    size_t mid_start = static_cast<size_t>(250.0f * fft_size_ / 44100.0f);
    size_t mid_end = static_cast<size_t>(4000.0f * fft_size_ / 44100.0f);
    float energy = 0.0f;
    for (size_t i = mid_start; i < mid_end && i < smoothed_magnitudes_.size(); ++i) {
        energy += smoothed_magnitudes_[i];
    }
    return std::min(energy / (mid_end - mid_start) * 10.0f, 1.0f);
}

float FFTProcessor::get_treble_energy() const {
    size_t treble_start = static_cast<size_t>(4000.0f * fft_size_ / 44100.0f);
    float energy = 0.0f;
    for (size_t i = treble_start; i < smoothed_magnitudes_.size(); ++i) {
        energy += smoothed_magnitudes_[i];
    }
    return std::min(energy / (smoothed_magnitudes_.size() - treble_start) * 10.0f, 1.0f);
}

float FFTProcessor::get_total_energy() const {
    float total = 0.0f;
    for (float m : smoothed_magnitudes_) {
        total += m;
    }
    return std::min(total / smoothed_magnitudes_.size() * 10.0f, 1.0f);
}

} // namespace aegis
