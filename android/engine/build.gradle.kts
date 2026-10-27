plugins {
  alias(libs.plugins.android.library)
}

android {
  namespace = "io.github.sajadinmaker.vpnbox.engine"
  compileSdk = 36

  defaultConfig {
    minSdk = 26
    ndk {
      abiFilters += listOf("arm64-v8a", "armeabi-v7a", "x86", "x86_64")
    }
    externalNativeBuild {
      cmake {
        cppFlags += "-std=c++23"
      }
    }
  }

  externalNativeBuild {
    cmake {
      path = file("src/main/cpp/CMakeLists.txt")
    }
  }

  // The OpenVPN3 core (libovpn3.so) with the Committed SWIG bindings under
  // src/main/java/net/openvpn/ovpn3.  Kotlin sources provide OpenVPN3Engine,
  // the TunnelEngine implementation on top of the OpenVPN 3 client API.
  sourceSets.getByName("main") {
    java.srcDir("src/main/java")
  }

  compileOptions {
    sourceCompatibility = JavaVersion.VERSION_17
    targetCompatibility = JavaVersion.VERSION_17
  }

  buildTypes {
    release {
      isMinifyEnabled = false
    }
  }
}
