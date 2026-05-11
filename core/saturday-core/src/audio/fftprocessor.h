#pragma once
#include <vector>

namespace aegis {
namespace audio {

class FFTProcessor {
public:
    FFTProcessor(int fftSize = 2048);
    ~FFTProcessor();

    void process(const float* input, int sampleCount);
    const float* getMagnitudes() const { return m_magnitudes.data(); }
    int getSize() const { return m_fftSize; }

private:
    int m_fftSize;
    std::vector<float> m_magnitudes;
    std::vector<float> m_window;
};

} // namespace audio
} // namespace aegis
