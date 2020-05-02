cmake_minimum_required(VERSION 3.5...3.15)
project(signjson)

# CXX Standard
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

set(CMAKE_POSITION_INDEPENDENT_CODE ON)

add_subdirectory(EmbeddedJSONSignature)

set(SRC "main.cpp")

add_executable(signjson ${SRC})
target_link_libraries(signjson EmbeddedJSONSignature)
target_include_directories(signjson PRIVATE args)

include(GNUInstallDirs)

install(TARGETS signjson
  RUNTIME DESTINATION "${CMAKE_INSTALL_BINDIR}"
)
