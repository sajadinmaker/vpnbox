# vpnbox engine — OpenVPN3 core build
# Adapted from the ics-openvpn (schwabe) build of the OpenVPN 3 client core
# (Apache-2.0/GPL build glue; the core itself is AGPLv3).  Sources:
#  - openvpn3/         submodule: github.com/schwabe/openvpn3 (pinned)
#  - openssl/          submodule: github.com/schwabe/platform_external_openssl
#  - asio/, fmt/, lz4/ submodules pinned to ics-openvpn's revisions
#  - lzo/              upstream lzo-2.10 extracted (GPLv2)
#  - ovpncli_wrap.cxx  SWIG-generated JNI wrapper (committed, see docs)
cmake_minimum_required(VERSION 3.22)
project("vpnbox-engine")

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_C_C_STANDARD 11)

# Make builds (like F-droid) happy that want reproducible builds
add_link_options("LINKER:--build-id=none")

include(tools.cmake)

# lzo — only the compression file set the core links in, like ics-openvpn
set(lzo_srcs
  lzo1.c
  lzo1_99.c
  lzo1a.c
  lzo1a_99.c
  lzo1b_1.c
  lzo1b_2.c
  lzo1b_3.c
  lzo1b_4.c
  lzo1b_5.c
  lzo1b_6.c
  lzo1b_7.c
  lzo1b_8.c
  lzo1b_9.c
  lzo1b_99.c
  lzo1b_9x.c
  lzo1b_cc.c
  lzo1b_d1.c
  lzo1b_d2.c
  lzo1b_rr.c
  lzo1b_xx.c
  lzo1c_1.c
  lzo1c_2.c
  lzo1c_3.c
  lzo1c_4.c
  lzo1c_5.c
  lzo1c_6.c
  lzo1c_7.c
  lzo1c_8.c
  lzo1c_9.c
  lzo1c_99.c
  lzo1c_9x.c
  lzo1c_cc.c
  lzo1c_d1.c
  lzo1c_d2.c
  lzo1c_rr.c
  lzo1c_xx.c
  lzo1f_1.c
  lzo1f_9x.c
  lzo1f_d1.c
  lzo1f_d2.c
  lzo1x_1.c
  lzo1x_1k.c
  lzo1x_1l.c
  lzo1x_1o.c
  lzo1x_9x.c
  lzo1x_d1.c
  lzo1x_d2.c
  lzo1x_d3.c
  lzo1x_o.c
  lzo1y_1.c
  lzo1y_9x.c
  lzo1y_d1.c
  lzo1y_d2.c
  lzo1y_d3.c
  lzo1y_o.c
  lzo1z_9x.c
  lzo1z_d1.c
  lzo1z_d2.c
  lzo1z_d3.c
  lzo2a_9x.c
  lzo2a_d1.c
  lzo2a_d2.c
  lzo_crc.c
  lzo_init.c
  lzo_ptr.c
  lzo_str.c
  lzo_util.c
  )

PREPEND(lzo_src_with_path "lzo/src" ${lzo_srcs})
add_library(lzo ${lzo_src_with_path})
target_include_directories(lzo PUBLIC "${CMAKE_CURRENT_SOURCE_DIR}/lzo/include")
if (${ANDROID_ABI} STREQUAL "armeabi-v7a")
    target_compile_options(lzo PRIVATE -O0)
endif()

# lz4 — decompressor only
set(lz4_srcs
  lz4.c
  )
PREPEND(lz4_src_with_path "lz4/lib/" ${lz4_srcs})
add_library(lz4 ${lz4_src_with_path})
target_include_directories(lz4 PUBLIC "${CMAKE_CURRENT_SOURCE_DIR}/lz4/lib")

# fmt — log formatting
set(FMT_TEST OFF)
set(FMT_DOC OFF)
set(FMT_INSTALL OFF)
add_subdirectory(fmt)

# OpenSSL (static crypto + ssl) built from the schwabe/platform_external_openssl checkout
set(OPENVPN3OSSL ON)
SET(SSLLIBTYPE STATIC)
SET(OPENSSL_PATH "openssl")
include(openssl/openssl.cmake)

# OpenVPN 3 client core
set(ovpn3_SRCS
        openvpn3/client/ovpncli.cpp
        openvpn3/openvpn/openssl/xkey/xkey_provider.c
        openvpn3/openvpn/openssl/xkey/xkey_helper.c
        openvpn3/openvpn/crypto/data_epoch.cpp
        ovpncli_wrap.cxx)

add_library(ovpn3 SHARED ${ovpn3_SRCS})

target_include_directories(
        ovpn3 PUBLIC
        ${CMAKE_CURRENT_SOURCE_DIR}/lzo/include
        ${CMAKE_CURRENT_SOURCE_DIR}/openvpn3
        ${CMAKE_CURRENT_SOURCE_DIR}/asio/asio/include
        ${CMAKE_CURRENT_SOURCE_DIR}/openvpn3/client
        ${CMAKE_CURRENT_SOURCE_DIR}/openssl/include
        )

target_compile_definitions(ovpn3 PRIVATE
        -DUSE_OPENSSL
        -DHAVE_CONFIG_H
        -DHAVE_LZO
        -DHAVE_LZ4
        -DASIO_STANDALONE
        -DUSE_ASIO
        -DOPENVPN_CORE_GIT_VERSION=\"29f38575\"
        -DOPENSSL_API_COMPAT=0x10200000L
        -DOPENVPN_ALLOW_INSECURE_CERTPROFILE
        -DENABLE_EXTERNAL_PKI
        )

target_link_libraries(ovpn3 crypto ssl lzo lz4 fmt log)
