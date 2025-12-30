function(
  create_paddle_tests
  BIN_PREFIX
  TEST_SRC_FILES
  TARGET_FOLDER
  DEPS_LIBRARIES
  INCLUDE_DIR
  USE_PADDLE_API)

  foreach(_test_file ${TEST_SRC_FILES})
    get_filename_component(_file_name ${_test_file} NAME_WE)
    set(_test_name ${BIN_PREFIX}${_file_name})
    add_executable(${_test_name} ${_test_file} ${TEST_BASE_FILES})
    add_dependencies(${_test_name} "googletest.git")
    target_link_libraries(
      ${_test_name} gtest gtest_main ${CMAKE_THREAD_LIBS_INIT}
      ${DEPS_LIBRARIES} ${Python3_LIBRARIES})
    target_include_directories(${_test_name} PRIVATE ${Python3_INCLUDE_DIRS})
    target_include_directories(${_test_name} PRIVATE ${INCLUDE_DIR})
    message(STATUS "include dir: ${INCLUDE_DIR}")
    target_compile_definitions(${_test_name}
                               PRIVATE USE_PADDLE_API=${USE_PADDLE_API})
    message(STATUS "USE_PADDLE_API: ${USE_PADDLE_API}")
    add_test(NAME ${_test_name} COMMAND ${_test_name})
    set_tests_properties(${_test_name} PROPERTIES TIMEOUT 5)
    set_target_properties(${_test_name} PROPERTIES RUNTIME_OUTPUT_DIRECTORY
                                                   "${TARGET_FOLDER}")
  endforeach()
endfunction()
