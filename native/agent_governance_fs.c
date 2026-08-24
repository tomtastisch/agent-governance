#define _GNU_SOURCE
#include <node_api.h>
#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

#if defined(__linux__)
#include <linux/fs.h>
#include <sys/syscall.h>
#elif defined(__APPLE__)
#include <sys/stdio.h>
#else
#error "unsupported platform"
#endif

static void throw_errno(napi_env env, const char *operation) {
  char message[256];
  snprintf(message, sizeof(message), "%s failed: %s", operation, strerror(errno));
  napi_value text, error, code;
  napi_create_string_utf8(env, message, NAPI_AUTO_LENGTH, &text);
  napi_create_error(env, NULL, text, &error);
  napi_create_string_utf8(env, errno == EEXIST ? "EEXIST" : "NATIVE_FS_ERROR", NAPI_AUTO_LENGTH, &code);
  napi_set_named_property(env, error, "code", code);
  napi_throw(env, error);
}

static int get_fd(napi_env env, napi_value value, int *result) {
  int32_t fd;
  if (napi_get_value_int32(env, value, &fd) != napi_ok || fd < 0) return 0;
  *result = fd;
  return 1;
}

static int get_u64(napi_env env, napi_value value, uint64_t *result) {
  bool lossless = false;
  return napi_get_value_bigint_uint64(env, value, result, &lossless) == napi_ok && lossless;
}

static int get_basename(napi_env env, napi_value value, char *buffer, size_t capacity) {
  size_t length = 0;
  if (napi_get_value_string_utf8(env, value, buffer, capacity, &length) != napi_ok || length == 0 || length >= capacity) return 0;
  if (strlen(buffer) != length || strcmp(buffer, ".") == 0 || strcmp(buffer, "..") == 0) return 0;
  return strchr(buffer, '/') == NULL && strchr(buffer, '\\') == NULL;
}

static napi_value secure_rename_no_replace(napi_env env, napi_callback_info info) {
  size_t argc = 8;
  napi_value argv[8];
  napi_get_cb_info(env, info, &argc, argv, NULL, NULL);
  int source_fd, destination_fd;
  uint64_t source_dev, source_ino, destination_dev, destination_ino;
  char source_name[256], destination_name[256];
  if (argc != 8 || !get_fd(env, argv[0], &source_fd) || !get_basename(env, argv[1], source_name, sizeof(source_name)) ||
      !get_u64(env, argv[2], &source_dev) || !get_u64(env, argv[3], &source_ino) || !get_fd(env, argv[4], &destination_fd) ||
      !get_basename(env, argv[5], destination_name, sizeof(destination_name)) || !get_u64(env, argv[6], &destination_dev) ||
      !get_u64(env, argv[7], &destination_ino)) {
    napi_throw_type_error(env, "NATIVE_FS_INVALID_ARGUMENT", "native rename requires valid directory fds, identities, and single basenames");
    return NULL;
  }
  struct stat source_directory, destination_directory, source_object;
  if (fstat(source_fd, &source_directory) != 0 || !S_ISDIR(source_directory.st_mode) ||
      (uint64_t)source_directory.st_dev != source_dev || (uint64_t)source_directory.st_ino != source_ino ||
      fstat(destination_fd, &destination_directory) != 0 || !S_ISDIR(destination_directory.st_mode) ||
      (uint64_t)destination_directory.st_dev != destination_dev || (uint64_t)destination_directory.st_ino != destination_ino) {
    errno = ESTALE;
    throw_errno(env, "directory identity validation");
    return NULL;
  }
  if (fstatat(source_fd, source_name, &source_object, AT_SYMLINK_NOFOLLOW) != 0) {
    throw_errno(env, "source type validation");
    return NULL;
  }
  if (!S_ISREG(source_object.st_mode)) {
    errno = EINVAL;
    throw_errno(env, "source type validation");
    return NULL;
  }
  int result;
#if defined(__linux__)
  result = (int)syscall(SYS_renameat2, source_fd, source_name, destination_fd, destination_name, RENAME_NOREPLACE);
#elif defined(__APPLE__)
  result = renameatx_np(source_fd, source_name, destination_fd, destination_name, RENAME_EXCL);
#endif
  if (result != 0) {
    throw_errno(env, "exclusive directory-relative rename");
    return NULL;
  }
  napi_value undefined;
  napi_get_undefined(env, &undefined);
  return undefined;
}

static napi_value initialize(napi_env env, napi_value exports) {
  napi_value function;
  napi_create_function(env, "secureRenameNoReplace", NAPI_AUTO_LENGTH, secure_rename_no_replace, NULL, &function);
  napi_set_named_property(env, exports, "secureRenameNoReplace", function);
  return exports;
}

NAPI_MODULE(NODE_GYP_MODULE_NAME, initialize)
