cmake_minimum_required(VERSION 3.20)
project(caprm_spatial_core LANGUAGES CXX)

# Replaces the five hand-copied g++ lines the README carried. The flags below
# are the ones every published measurement was taken under; changing them
# invalidates a comparison against a stored benchmark record.

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

if(NOT CMAKE_BUILD_TYPE AND NOT CMAKE_CONFIGURATION_TYPES)
    set(CMAKE_BUILD_TYPE Release CACHE STRING "" FORCE)
endif()

set(SRC ${CMAKE_CURRENT_SOURCE_DIR}/src)

# The ladder is built as five separate translation units, not as a library.
# Each source #includes the one below it so the distance kernel and the tie
# rule are reused rather than reimplemented, which is what lets adjacent rungs
# differ by exactly one variable. Linking them into one binary would defeat
# that: the renamed mains would collide and the reuse would stop being visible
# in the source.

add_executable(fema_pip_dev                ${SRC}/fema_pip_dev.cpp)
add_executable(water_distance_bruteforce   ${SRC}/water_distance_bruteforce.cpp)
add_executable(water_distance_indexed      ${SRC}/water_distance_indexed.cpp)
add_executable(water_distance_segment_bvh  ${SRC}/water_distance_segment_bvh.cpp)
add_executable(water_distance_hilbert      ${SRC}/water_distance_hilbert.cpp)

set(LADDER
    water_distance_bruteforce
    water_distance_indexed
    water_distance_segment_bvh
    water_distance_hilbert
)

foreach(target fema_pip_dev ${LADDER})
    if(MSVC)
        target_compile_options(${target} PRIVATE /O2 /W4)
    else()
        target_compile_options(${target} PRIVATE -O2 -Wall -Wextra)
    endif()
endforeach()

# -ffp-contract=off is REQUIRED for the Hilbert binary and is not a style
# choice. It changes nothing on baseline SSE2, but a -march=native build on
# Haswell or later can contract a + b*x into a fused multiply-add and shift the
# RMI's normalized input. The manifest probe catches that at load; this flag
# prevents it from happening.
if(NOT MSVC)
    target_compile_options(water_distance_hilbert PRIVATE -ffp-contract=off)
else()
    target_compile_options(water_distance_hilbert PRIVATE /fp:precise)
endif()

# SEED_WINDOW is a compile-time parameter. B6b built nine binaries across nine
# windows and verified byte-neutrality at every one -- with a positive control,
# after a first attempt passed the neutrality gate on binaries whose source
# never referenced the macro.
#
#   cmake --build build --target water_distance_hilbert_w8 ...
set(SEED_WINDOWS 8 16 32 64 128 256 512 1024 2048)
foreach(w ${SEED_WINDOWS})
    set(target water_distance_hilbert_w${w})
    add_executable(${target} EXCLUDE_FROM_ALL ${SRC}/water_distance_hilbert.cpp)
    target_compile_definitions(${target} PRIVATE CAPRM_SEED_WINDOW=${w})
    if(MSVC)
        target_compile_options(${target} PRIVATE /O2 /W4 /fp:precise)
    else()
        target_compile_options(${target} PRIVATE -O2 -Wall -Wextra -ffp-contract=off)
    endif()
endforeach()

add_custom_target(seed_window_sweep)
foreach(w ${SEED_WINDOWS})
    add_dependencies(seed_window_sweep water_distance_hilbert_w${w})
endforeach()

# Native suites for geometric invariants that have no Python counterpart to
# compare against. The primary correctness claim still rests on field-by-field
# comparison with the Python reference; these cover what that cannot reach.
set(NATIVE_TEST_DIR ${CMAKE_CURRENT_SOURCE_DIR}/../../tests/cpp)
if(EXISTS ${NATIVE_TEST_DIR}/test_water_segment_bvh.cpp)
    enable_testing()
    foreach(suite test_water_segment_bvh test_water_segment_bvh_verify_modes)
        add_executable(${suite} ${NATIVE_TEST_DIR}/${suite}.cpp)
        if(MSVC)
            target_compile_options(${suite} PRIVATE /O2 /W4)
        else()
            target_compile_options(${suite} PRIVATE -O2 -Wall -Wextra)
        endif()
        target_include_directories(${suite} PRIVATE ${SRC})
        add_test(NAME ${suite} COMMAND ${suite})
    endforeach()
endif()

# Binaries land where the Python harness already looks for them.
set_target_properties(
    fema_pip_dev ${LADDER}
    PROPERTIES RUNTIME_OUTPUT_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/build
)
foreach(w ${SEED_WINDOWS})
    set_target_properties(
        water_distance_hilbert_w${w}
        PROPERTIES RUNTIME_OUTPUT_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/build
    )
endforeach()
