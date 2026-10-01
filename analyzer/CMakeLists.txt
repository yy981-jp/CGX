set(EXE_NAME "analyzer")

add_subdirectory(${CMAKE_SOURCE_DIR}/external/CLI11 ${CMAKE_BINARY_DIR}/CLI11)

file(GLOB_RECURSE SOURCES src/*.cpp)

add_executable(${EXE_NAME} ${SOURCES})

target_include_directories(${EXE_NAME} PRIVATE
	${CMAKE_SOURCE_DIR}/analyzer/src
	${CMAKE_SOURCE_DIR}/external
)

target_link_libraries(${EXE_NAME} PRIVATE CLI11::CLI11)
