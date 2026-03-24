#pragma once

#include <string>
#include <unordered_map>
#include <vector>

#include <GL/gl.h>

namespace aegis {

/**
 * @class Shader
 * @brief OpenGL shader program wrapper with RAII resource management
 * 
 * Loads, compiles, and links GLSL shaders. Provides uniform
 * variable management and automatic cleanup on destruction.
 */
class Shader {
public:
    /**
     * @brief Default constructor - creates null shader
     */
    Shader() = default;

    /**
     * @brief Construct shader from source code
     * @param vertex_source GLSL vertex shader source
     * @param fragment_source GLSL fragment shader source
     * @param geometry_source Optional GLSL geometry shader source
     */
    Shader(const std::string& vertex_source, 
           const std::string& fragment_source,
           const std::string& geometry_source = "");

    /**
     * @brief Destructor - releases GPU resources
     */
    ~Shader();

    // Non-copyable
    Shader(const Shader&) = delete;
    Shader& operator=(const Shader&) = delete;

    // Movable
    Shader(Shader&& other) noexcept;
    Shader& operator=(Shader&& other) noexcept;

    /**
     * @brief Check if shader is valid
     */
    bool is_valid() const { return program_id_ != 0; }
    explicit operator bool() const { return is_valid(); }

    /**
     * @brief Use this shader program
     */
    void use() const;

    /**
     * @brief Unbind shader
     */
    static void unbind();

    // Uniform setters
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

    /**
     * @brief Get OpenGL program ID
     */
    GLuint get_program_id() const { return program_id_; }

private:
    GLuint compile_shader(const std::string& source, GLenum type);
    GLint get_uniform_location(const std::string& name);

    GLuint program_id_ = 0;
    std::unordered_map<std::string, GLint> uniform_cache_;
};

/**
 * @class ShaderManager
 * @brief Manages multiple shader programs
 */
class ShaderManager {
public:
    ShaderManager() = default;
    ~ShaderManager() = default;

    /**
     * @brief Load and compile a shader program
     * @param name Identifier for the shader
     * @param vertex_path Path to vertex shader
     * @param fragment_path Path to fragment shader
     * @param geometry_path Optional path to geometry shader
     * @return true if successful
     */
    bool load(const std::string& name,
              const std::string& vertex_path,
              const std::string& fragment_path,
              const std::string& geometry_path = "");

    /**
     * @brief Add shader from source code
     */
    bool add_from_source(const std::string& name,
                         const std::string& vertex_source,
                         const std::string& fragment_source,
                         const std::string& geometry_source = "");

    /**
     * @brief Get shader by name
     */
    Shader* get(const std::string& name);
    const Shader* get(const std::string& name) const;

    /**
     * @brief Check if shader exists
     */
    bool exists(const std::string& name) const;

    /**
     * @brief Remove shader
     */
    void remove(const std::string& name);

    /**
     * @brief Clear all shaders
     */
    void clear();

    /**
     * @brief Get number of loaded shaders
     */
    size_t count() const { return shaders_.size(); }

private:
    std::string read_file(const std::string& path);
    std::unordered_map<std::string, Shader> shaders_;
};

/**
 * @struct ShaderSource
 * @brief Container for raw shader source code
 */
struct ShaderSource {
    std::string vertex;
    std::string fragment;
    std::string geometry;
};

} // namespace aegis
