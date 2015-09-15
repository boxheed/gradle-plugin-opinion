# Gradle plugin build script opinion

This library provides defaults and opinions for gradle plugin development for the com.fizzpod gradle plugins. This is not a general purpose library and should not directly be used for any other purpose.

This library uses the `com.fizzpod.pater-build` plugin to apply the build script included in this library to the root project.

## Usage
The following should be used in the build script to apply the defaults.
```
buildscript {
	repositories {
		mavenLocal()
		jcenter()
		maven {
      url "https://plugins.gradle.org/m2/"
    }
		maven {
			url "https://dl.bintray.com/boxhead/maven/"
		}
	}
	dependencies {
			classpath ('com.fizzpod:gradle-plugin-opinion:0.1.4') {
				exclude group: 'com.fizzpod', module: 'gradle-gitignore-plugin'
			}
    }
}

apply plugin: 'com.fizzpod.pater-build'

```

## Defaults

See the [com-fizzpod-opinion-gradle-plugin.gradle](./src/main/resources/META-INF/pater-build/com-fizzpod-opinion-gradle-plugin.gradle) for the details of the included plugins and defaults.
