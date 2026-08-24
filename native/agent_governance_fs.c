#define _GNU_SOURCE
#include <node_api.h>
#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdatomic.h>
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

static uint64_t stat_mtime_ns(const struct stat *value) {
#if defined(__APPLE__)
  return (uint64_t)value->st_mtimespec.tv_sec * 1000000000ULL + (uint64_t)value->st_mtimespec.tv_nsec;
#else
  return (uint64_t)value->st_mtim.tv_sec * 1000000000ULL + (uint64_t)value->st_mtim.tv_nsec;
#endif
}

static uint64_t stat_ctime_ns(const struct stat *value) {
#if defined(__APPLE__)
  return (uint64_t)value->st_ctimespec.tv_sec * 1000000000ULL + (uint64_t)value->st_ctimespec.tv_nsec;
#else
  return (uint64_t)value->st_ctim.tv_sec * 1000000000ULL + (uint64_t)value->st_ctim.tv_nsec;
#endif
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

static napi_value secure_rename_directory_no_replace(napi_env env, napi_callback_info info) {
  size_t argc = 10; napi_value argv[10]; napi_get_cb_info(env, info, &argc, argv, NULL, NULL);
  int source_fd, destination_fd; uint64_t source_dev, source_ino, object_dev, object_ino, destination_dev, destination_ino; char source_name[256], destination_name[256];
  if (argc != 10 || !get_fd(env, argv[0], &source_fd) || !get_basename(env, argv[1], source_name, sizeof(source_name)) || !get_u64(env, argv[2], &source_dev) || !get_u64(env, argv[3], &source_ino) || !get_u64(env, argv[4], &object_dev) || !get_u64(env, argv[5], &object_ino) || !get_fd(env, argv[6], &destination_fd) || !get_basename(env, argv[7], destination_name, sizeof(destination_name)) || !get_u64(env, argv[8], &destination_dev) || !get_u64(env, argv[9], &destination_ino)) { napi_throw_type_error(env, "NATIVE_FS_INVALID_ARGUMENT", "native directory rename requires valid directory fds, identities, and single basenames"); return NULL; }
  struct stat source_directory, destination_directory, source_object;
  if (fstat(source_fd, &source_directory) != 0 || !S_ISDIR(source_directory.st_mode) || (uint64_t)source_directory.st_dev != source_dev || (uint64_t)source_directory.st_ino != source_ino || fstat(destination_fd, &destination_directory) != 0 || !S_ISDIR(destination_directory.st_mode) || (uint64_t)destination_directory.st_dev != destination_dev || (uint64_t)destination_directory.st_ino != destination_ino || fstatat(source_fd, source_name, &source_object, AT_SYMLINK_NOFOLLOW) != 0 || !S_ISDIR(source_object.st_mode) || (uint64_t)source_object.st_dev != object_dev || (uint64_t)source_object.st_ino != object_ino) { errno = ESTALE; throw_errno(env, "directory rename identity validation"); return NULL; }
  int result;
#if defined(__linux__)
  result = (int)syscall(SYS_renameat2, source_fd, source_name, destination_fd, destination_name, RENAME_NOREPLACE);
#elif defined(__APPLE__)
  result = renameatx_np(source_fd, source_name, destination_fd, destination_name, RENAME_EXCL);
#endif
  if (result != 0) { throw_errno(env, "exclusive directory-relative directory rename"); return NULL; }
  napi_value undefined; napi_get_undefined(env, &undefined); return undefined;
}

static void cleanup_exclusive_create(int directory_fd, const char *name, const struct stat *created) {
  struct stat visible;
  if (fstatat(directory_fd, name, &visible, AT_SYMLINK_NOFOLLOW) == 0 && S_ISREG(visible.st_mode) &&
      visible.st_dev == created->st_dev && visible.st_ino == created->st_ino && visible.st_mode == created->st_mode) {
    (void)unlinkat(directory_fd, name, 0);
  }
}

static napi_value secure_create_no_replace(napi_env env, napi_callback_info info) {
  size_t argc = 5;
  napi_value argv[5];
  napi_get_cb_info(env, info, &argc, argv, NULL, NULL);
  int directory_fd;
  uint64_t directory_dev, directory_ino;
  char name[256];
  void *content;
  size_t content_length;
  if (argc != 5 || !get_fd(env, argv[0], &directory_fd) || !get_basename(env, argv[1], name, sizeof(name)) ||
      !get_u64(env, argv[2], &directory_dev) || !get_u64(env, argv[3], &directory_ino) ||
      napi_get_buffer_info(env, argv[4], &content, &content_length) != napi_ok) {
    napi_throw_type_error(env, "NATIVE_FS_INVALID_ARGUMENT", "native create requires a valid directory fd, identity, basename, and buffer");
    return NULL;
  }
  struct stat directory;
  if (fstat(directory_fd, &directory) != 0 || !S_ISDIR(directory.st_mode) ||
      (uint64_t)directory.st_dev != directory_dev || (uint64_t)directory.st_ino != directory_ino) {
    errno = ESTALE;
    throw_errno(env, "directory identity validation");
    return NULL;
  }
  int output = openat(directory_fd, name, O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW, 0600);
  if (output < 0) {
    throw_errno(env, "exclusive directory-relative create");
    return NULL;
  }
  struct stat created;
  if (fstat(output, &created) != 0 || !S_ISREG(created.st_mode)) {
    int saved = errno == 0 ? ESTALE : errno;
    close(output);
    errno = saved;
    throw_errno(env, "exclusive create identity validation");
    return NULL;
  }
#ifdef AGENT_GOVERNANCE_TEST_FAIL_AFTER_CREATE
  errno = EIO;
  int injected = errno;
  cleanup_exclusive_create(directory_fd, name, &created);
  close(output);
  errno = injected;
  throw_errno(env, "directory-relative write");
  return NULL;
#endif
  size_t written = 0;
  while (written < content_length) {
    ssize_t count = write(output, (const char *)content + written, content_length - written);
    if (count <= 0) {
      if (count == 0) errno = EIO;
      int saved = errno;
      cleanup_exclusive_create(directory_fd, name, &created);
      close(output);
      errno = saved;
      throw_errno(env, "directory-relative write");
      return NULL;
    }
    written += (size_t)count;
  }
  if (fsync(output) != 0) {
    int saved = errno;
    cleanup_exclusive_create(directory_fd, name, &created);
    close(output);
    errno = saved;
    throw_errno(env, "directory-relative file sync");
    return NULL;
  }
  int close_result = close(output);
#ifdef AGENT_GOVERNANCE_TEST_FAIL_CREATE_CLOSE
  if (close_result == 0) { errno = EIO; close_result = -1; }
#endif
  if (close_result != 0) {
    int saved = errno;
    cleanup_exclusive_create(directory_fd, name, &created);
    errno = saved;
    throw_errno(env, "directory-relative file close");
    return NULL;
  }
  napi_value undefined;
  napi_get_undefined(env, &undefined);
  return undefined;
}

static napi_value secure_write_file(napi_env env, napi_callback_info info) {
  size_t argc = 11; napi_value argv[11]; napi_get_cb_info(env, info, &argc, argv, NULL, NULL);
  int directory_fd; uint64_t directory_dev, directory_ino, object_dev, object_ino, object_mode, object_size, object_mtime_ns, object_ctime_ns; char name[256]; void *content; size_t content_length;
  if (argc != 11 || !get_fd(env, argv[0], &directory_fd) || !get_basename(env, argv[1], name, sizeof(name)) || !get_u64(env, argv[2], &directory_dev) || !get_u64(env, argv[3], &directory_ino) || !get_u64(env, argv[4], &object_dev) || !get_u64(env, argv[5], &object_ino) || !get_u64(env, argv[6], &object_mode) || !get_u64(env, argv[7], &object_size) || !get_u64(env, argv[8], &object_mtime_ns) || !get_u64(env, argv[9], &object_ctime_ns) || napi_get_buffer_info(env, argv[10], &content, &content_length) != napi_ok) { napi_throw_type_error(env, "NATIVE_FS_INVALID_ARGUMENT", "native write requires valid directory and object snapshot, basename, and buffer"); return NULL; }
  struct stat directory; if (fstat(directory_fd, &directory) != 0 || !S_ISDIR(directory.st_mode) || (uint64_t)directory.st_dev != directory_dev || (uint64_t)directory.st_ino != directory_ino) { errno = ESTALE; throw_errno(env, "directory identity validation"); return NULL; }
  static _Atomic unsigned long counter = 0; unsigned long sequence = atomic_fetch_add(&counter, 1) + 1; char temporary[256]; int length = snprintf(temporary, sizeof(temporary), ".ag-%ld-%lu.tmp", (long)getpid(), sequence); if (length <= 0 || (size_t)length >= sizeof(temporary)) { errno = ENAMETOOLONG; throw_errno(env, "temporary basename generation"); return NULL; }
  int output = openat(directory_fd, temporary, O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW, 0600); if (output < 0) { throw_errno(env, "exclusive temporary create"); return NULL; }
  struct stat created; if (fstat(output, &created) != 0 || !S_ISREG(created.st_mode)) { int saved = errno == 0 ? ESTALE : errno; close(output); errno = saved; throw_errno(env, "temporary file identity validation"); return NULL; }
  size_t written = 0; while (written < content_length) { ssize_t count = write(output, (const char *)content + written, content_length - written); if (count <= 0) { if (count == 0) errno = EIO; int saved = errno; close(output); cleanup_exclusive_create(directory_fd, temporary, &created); errno = saved; throw_errno(env, "directory-relative write"); return NULL; } written += (size_t)count; }
  if (fsync(output) != 0) { int saved = errno; close(output); cleanup_exclusive_create(directory_fd, temporary, &created); errno = saved; throw_errno(env, "directory-relative file sync"); return NULL; }
  if (fstat(output, &created) != 0 || !S_ISREG(created.st_mode)) { int saved = errno == 0 ? ESTALE : errno; close(output); cleanup_exclusive_create(directory_fd, temporary, &created); errno = saved; throw_errno(env, "temporary file snapshot validation"); return NULL; }
  if (close(output) != 0) { int saved = errno; cleanup_exclusive_create(directory_fd, temporary, &created); errno = saved; throw_errno(env, "directory-relative file close"); return NULL; }
#ifdef AGENT_GOVERNANCE_TEST_SWAP_REPLACE_TEMP
  char retired[256]; int retired_length = snprintf(retired, sizeof(retired), "%s.retired", temporary); if (retired_length <= 0 || (size_t)retired_length >= sizeof(retired) || renameat(directory_fd, temporary, directory_fd, retired) != 0) { throw_errno(env, "test temporary rename"); return NULL; }
  int foreign = openat(directory_fd, temporary, O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW, 0600); if (foreign < 0 || write(foreign, "foreign\n", 8) != 8 || close(foreign) != 0) { throw_errno(env, "test foreign temporary create"); return NULL; }
#endif
  struct stat visible_temporary, object; if (fstatat(directory_fd, temporary, &visible_temporary, AT_SYMLINK_NOFOLLOW) != 0 || !S_ISREG(visible_temporary.st_mode) || visible_temporary.st_dev != created.st_dev || visible_temporary.st_ino != created.st_ino || visible_temporary.st_mode != created.st_mode || visible_temporary.st_size != created.st_size || stat_mtime_ns(&visible_temporary) != stat_mtime_ns(&created) || stat_ctime_ns(&visible_temporary) != stat_ctime_ns(&created)) { errno = ESTALE; throw_errno(env, "temporary file identity validation"); return NULL; }
  if (fstatat(directory_fd, name, &object, AT_SYMLINK_NOFOLLOW) != 0 || !S_ISREG(object.st_mode) || (uint64_t)object.st_dev != object_dev || (uint64_t)object.st_ino != object_ino || (uint64_t)object.st_mode != object_mode || (uint64_t)object.st_size != object_size || stat_mtime_ns(&object) != object_mtime_ns || stat_ctime_ns(&object) != object_ctime_ns) { int saved = errno == 0 ? ESTALE : errno; cleanup_exclusive_create(directory_fd, temporary, &created); errno = saved; throw_errno(env, "replace object identity validation"); return NULL; }
  if (renameat(directory_fd, temporary, directory_fd, name) != 0) { int saved = errno; cleanup_exclusive_create(directory_fd, temporary, &created); errno = saved; throw_errno(env, "directory-relative file replace"); return NULL; }
  napi_value undefined; napi_get_undefined(env, &undefined); return undefined;
}

static napi_value secure_remove_file(napi_env env, napi_callback_info info) {
  size_t argc = 10; napi_value argv[10]; napi_get_cb_info(env, info, &argc, argv, NULL, NULL); int directory_fd; uint64_t directory_dev, directory_ino, object_dev, object_ino, object_mode, object_size, object_mtime_ns, object_ctime_ns; char name[256];
  if (argc != 10 || !get_fd(env, argv[0], &directory_fd) || !get_basename(env, argv[1], name, sizeof(name)) || !get_u64(env, argv[2], &directory_dev) || !get_u64(env, argv[3], &directory_ino) || !get_u64(env, argv[4], &object_dev) || !get_u64(env, argv[5], &object_ino) || !get_u64(env, argv[6], &object_mode) || !get_u64(env, argv[7], &object_size) || !get_u64(env, argv[8], &object_mtime_ns) || !get_u64(env, argv[9], &object_ctime_ns)) { napi_throw_type_error(env, "NATIVE_FS_INVALID_ARGUMENT", "native unlink requires valid parent and object snapshot and a basename"); return NULL; }
  struct stat directory, object; if (fstat(directory_fd, &directory) != 0 || !S_ISDIR(directory.st_mode) || (uint64_t)directory.st_dev != directory_dev || (uint64_t)directory.st_ino != directory_ino || fstatat(directory_fd, name, &object, AT_SYMLINK_NOFOLLOW) != 0 || !S_ISREG(object.st_mode) || (uint64_t)object.st_dev != object_dev || (uint64_t)object.st_ino != object_ino || (uint64_t)object.st_mode != object_mode || (uint64_t)object.st_size != object_size || stat_mtime_ns(&object) != object_mtime_ns || stat_ctime_ns(&object) != object_ctime_ns) { errno = ESTALE; throw_errno(env, "unlink identity and type validation"); return NULL; }
  if (unlinkat(directory_fd, name, 0) != 0) { throw_errno(env, "directory-relative unlink"); return NULL; } napi_value undefined; napi_get_undefined(env, &undefined); return undefined;
}

static napi_value secure_create_directory(napi_env env, napi_callback_info info) {
  size_t argc = 4; napi_value argv[4]; napi_get_cb_info(env, info, &argc, argv, NULL, NULL); int directory_fd; uint64_t directory_dev, directory_ino; char name[256];
  if (argc != 4 || !get_fd(env, argv[0], &directory_fd) || !get_basename(env, argv[1], name, sizeof(name)) || !get_u64(env, argv[2], &directory_dev) || !get_u64(env, argv[3], &directory_ino)) { napi_throw_type_error(env, "NATIVE_FS_INVALID_ARGUMENT", "native mkdir requires a valid parent fd, identity, and basename"); return NULL; }
  struct stat directory; if (fstat(directory_fd, &directory) != 0 || !S_ISDIR(directory.st_mode) || (uint64_t)directory.st_dev != directory_dev || (uint64_t)directory.st_ino != directory_ino) { errno = ESTALE; throw_errno(env, "mkdir parent identity validation"); return NULL; }
  if (mkdirat(directory_fd, name, 0700) != 0) { throw_errno(env, "exclusive directory-relative mkdir"); return NULL; } napi_value undefined; napi_get_undefined(env, &undefined); return undefined;
}

static napi_value secure_remove_directory(napi_env env, napi_callback_info info) {
  size_t argc = 6; napi_value argv[6]; napi_get_cb_info(env, info, &argc, argv, NULL, NULL); int directory_fd; uint64_t directory_dev, directory_ino, object_dev, object_ino; char name[256];
  if (argc != 6 || !get_fd(env, argv[0], &directory_fd) || !get_basename(env, argv[1], name, sizeof(name)) || !get_u64(env, argv[2], &directory_dev) || !get_u64(env, argv[3], &directory_ino) || !get_u64(env, argv[4], &object_dev) || !get_u64(env, argv[5], &object_ino)) { napi_throw_type_error(env, "NATIVE_FS_INVALID_ARGUMENT", "native rmdir requires a valid parent fd, parent identity, basename, and directory identity"); return NULL; }
  struct stat directory, object; if (fstat(directory_fd, &directory) != 0 || !S_ISDIR(directory.st_mode) || (uint64_t)directory.st_dev != directory_dev || (uint64_t)directory.st_ino != directory_ino || fstatat(directory_fd, name, &object, AT_SYMLINK_NOFOLLOW) != 0 || !S_ISDIR(object.st_mode) || (uint64_t)object.st_dev != object_dev || (uint64_t)object.st_ino != object_ino) { errno = ESTALE; throw_errno(env, "rmdir identity and type validation"); return NULL; }
  if (unlinkat(directory_fd, name, AT_REMOVEDIR) != 0) { throw_errno(env, "directory-relative rmdir"); return NULL; } napi_value undefined; napi_get_undefined(env, &undefined); return undefined;
}

static napi_value initialize(napi_env env, napi_value exports) {
  napi_value function;
  napi_create_function(env, "secureRenameNoReplace", NAPI_AUTO_LENGTH, secure_rename_no_replace, NULL, &function);
  napi_set_named_property(env, exports, "secureRenameNoReplace", function);
  napi_create_function(env, "secureCreateNoReplace", NAPI_AUTO_LENGTH, secure_create_no_replace, NULL, &function);
  napi_set_named_property(env, exports, "secureCreateNoReplace", function);
  napi_create_function(env, "secureCreateDirectory", NAPI_AUTO_LENGTH, secure_create_directory, NULL, &function);
  napi_set_named_property(env, exports, "secureCreateDirectory", function);
  napi_create_function(env, "secureWriteFile", NAPI_AUTO_LENGTH, secure_write_file, NULL, &function);
  napi_set_named_property(env, exports, "secureWriteFile", function);
  napi_create_function(env, "secureRemoveFile", NAPI_AUTO_LENGTH, secure_remove_file, NULL, &function);
  napi_set_named_property(env, exports, "secureRemoveFile", function);
  napi_create_function(env, "secureRemoveDirectory", NAPI_AUTO_LENGTH, secure_remove_directory, NULL, &function);
  napi_set_named_property(env, exports, "secureRemoveDirectory", function);
  napi_create_function(env, "secureRenameDirectoryNoReplace", NAPI_AUTO_LENGTH, secure_rename_directory_no_replace, NULL, &function);
  napi_set_named_property(env, exports, "secureRenameDirectoryNoReplace", function);
  return exports;
}

NAPI_MODULE(NODE_GYP_MODULE_NAME, initialize)
