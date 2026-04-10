#pragma once

#include <string>
#include <unordered_map>
#include <vector>

#include <GL/gl.h>

namespace aegis {

class Shader {
public:
    Shader() = default;

    Shader(const std::string& vertex_source, 
           const std::string& fragment_source,
           const std::string& geometry_source = "");

    ~Shader();

    Shader(const Shader&) = delete;
    Shader& operator=(const Shader&) = delete;

    Shader(Shader&& other) noexcept;
    Shader& operator=(Shader&& other) noexcept;

    bool is_valid() const { return program_id_ != 0; }
    explicit operator bool() const { return is_valid(); }

    void use() const;

    static void unbind();

    void set_int(const std::string& name, int value);
    void set_float(const std::string& name, float value);
    void set_vec2(const std::string& name, float x, float y);
    void set_vec2(const std::string& name, const float* value);
    void set_vec3(const std::string& name, float x, float y, float z);
    void set_vec3(const std::string& name, const float* value);
    void set_vec4(const std::string& name, float x, float y, float z, float w);
    void set_vec4(const std::string& name, const float* value);
    void set_mat3(const std::string& name, const float* value, bool transpose = false);
    void set_mat4(const std::string& name, const float* value, bool transpose = false);

    GLuint get_program_id() const { return program_id_; }

private:
    GLuint compile_shader(const std::string& source, GLenum type);
    GLint get_uniform_location(const std::string& name);

    GLuint program_id_ = 0;
    std::unordered_map<std::string, GLint> uniform_cache_;
};

class ShaderManager {
public:
    ShaderManager() = default;
    ~ShaderManager() = default;

    bool load(const std::string& name,
              const std::string& vertex_path,
              const std::string& fragment_path,
              const std::string& geometry_path = "");

    bool add_from_source(const std::string& name,
                         const std::string& vertex_source,
                         const std::string& fragment_source,
                         const std::string& geometry_source = "");

    Shader* get(const std::string& name);
    const Shader* get(const std::string& name) const;

    bool exists(const std::string& name) const;

    void remove(const std::string& name);

    void clear();

    size_t count() const { return shaders_.size(); }

private:
    std::string read_file(const std::string& path);
    std::unordered_map<std::string, Shader> shaders_;
};

struct ShaderSource {
    std::string vertex;
    std::string fragment;
    std::string geometry;
};

} // namespace aegis
