#pragma once

#include <string>

namespace aegis {

/**
 * @class Texture
 * @brief OpenGL texture wrapper
 */
class Texture {
public:
    Texture();
    ~Texture();
    
    bool load_from_file(const std::string& path);
    bool create(int width, int height, int channels, const unsigned char* data);
    
    void bind() const;
    static void unbind();
    
    int get_width() const { return width_; }
    int get_height() const { return height_; }
    
private:
    unsigned int texture_id_ = 0;
    int width_ = 0;
    int height_ = 0;
    int channels_ = 0;
};

} // namespace aegis
