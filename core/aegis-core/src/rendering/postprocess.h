#pragma once

namespace aegis {
namespace rendering {

class PostProcess {
public:
    PostProcess();
    ~PostProcess();

    void applyBloom(float intensity);
    void applyBlur(int radius);
    void applyVignette(float intensity);

private:
    float m_bloomIntensity = 1.0f;
    float m_vignetteIntensity = 0.5f;
};

} // namespace rendering
} // namespace aegis
