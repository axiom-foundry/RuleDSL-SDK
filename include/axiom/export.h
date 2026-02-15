#pragma once
// Export macros for shared library visibility.

#if defined(_WIN32) || defined(__CYGWIN__)
#  if defined(AXIOM_SHARED)
#    if defined(AXIOM_BUILD)
#      define AXIOM_API __declspec(dllexport)
#    else
#      define AXIOM_API __declspec(dllimport)
#    endif
#  else
#    define AXIOM_API
#  endif
#else
#  if defined(AXIOM_SHARED) && defined(__GNUC__)
#    define AXIOM_API __attribute__((visibility("default")))
#  else
#    define AXIOM_API
#  endif
#endif
