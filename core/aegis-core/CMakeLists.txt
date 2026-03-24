cmake_minimum_required(VERSION 3.16)
project(AEGISCore VERSION 2.0.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(OpenGL REQUIRED)

set(GLFW_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/third_party/glfw/glfw-3.4.bin.WIN64")
set(GLFW_INCLUDE_DIR "${GLFW_ROOT}/include")
set(GLFW_LIBRARY "${GLFW_ROOT}/lib-vc2022/glfw3.lib")

include_directories(${GLFW_INCLUDE_DIR})

set(SOURCES
    src/main.cpp
)

add_executable(aegis-core ${SOURCES})

set(LAUNCHER_SOURCES
    src/aegis_launcher.cpp
)

add_executable(AEGIS ${LAUNCHER_SOURCES})

target_include_directories(aegis-core PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/src
)

target_link_libraries(aegis-core PRIVATE
    ${GLFW_LIBRARY}
    OpenGL::GL
)

if(WIN32)
    target_link_libraries(aegis-core PRIVATE winmm.lib)
    target_link_libraries(AEGIS PRIVATE ws2_32.lib)
endif()

target_compile_options(aegis-core PRIVATE /W3 /utf-8)
target_compile_options(AEGIS PRIVATE /W3 /utf-8)

set_target_properties(aegis-core PROPERTIES
    RUNTIME_OUTPUT_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/bin
    OUTPUT_NAME "aegis-core"
)

set_target_properties(AEGIS PROPERTIES
    RUNTIME_OUTPUT_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/bin
    OUTPUT_NAME "AEGIS"
)
