#!/usr/bin/env python3
"""Patch a moonlight-android checkout into the NimbusSeat all-in-one app.

 * applicationId  -> app.nimbusseat.client (per upstream's request not to ship
   com.limelight builds)
 * app label      -> NimbusSeat
 * release build  -> signed with the NimbusSeat release keystore (env vars)
 * launcher       -> NimbusSeat MainActivity (embedded Moonlight PcView is
   opened from it with one tap)

Usage: python3 patch_moonlight.py <moonlight-android checkout dir>
"""
import re
import sys
from pathlib import Path

root = Path(sys.argv[1])
gradle = root / "app" / "build.gradle"
manifest = root / "app" / "src" / "main" / "AndroidManifest.xml"

# ---- build.gradle ---------------------------------------------------------
g = gradle.read_text()

g = g.replace('applicationId "com.limelight"', 'applicationId "app.nimbusseat.client"')
g = g.replace('versionName "12.1"', 'versionName "0.2.0-ml12.1"')

# release buildType: replace the .unofficial suffix with our signing config
g = g.replace('applicationIdSuffix ".unofficial"', "signingConfig signingConfigs.nimbus")

# release labels
g = g.replace('resValue "string", "app_label", "Moonlight"\n',
              'resValue "string", "app_label", "NimbusSeat"\n')
g = g.replace('resValue "string", "app_label_root", "Moonlight (Root)"',
              'resValue "string", "app_label_root", "NimbusSeat (Root)"')

# add signingConfigs right after the android { opening
signing = """
    signingConfigs {
        nimbus {
            storeFile file(System.getenv("NIMBUS_KEYSTORE"))
            storePassword System.getenv("NIMBUS_STOREPASS")
            keyAlias System.getenv("NIMBUS_KEYALIAS") ?: "nimbusseat"
            keyPassword System.getenv("NIMBUS_STOREPASS")
        }
    }
"""
g = g.replace("android {", "android {" + signing, 1)
gradle.write_text(g)
print("patched", gradle)

# ---- AndroidManifest.xml ----------------------------------------------------
m = manifest.read_text()

# PcView keeps MAIN but loses the launcher categories (single app icon).
m = m.replace(
    '<category android:name="android.intent.category.LAUNCHER" />\n', "", 1)
m = m.replace(
    '<category android:name="android.intent.category.LEANBACK_LAUNCHER" />\n', "", 1)

activity = """
        <activity
            android:name="app.nimbusseat.client.CloudSeatActivity"
            android:label="NimbusSeat Cloud"
            android:exported="false"
            android:configChanges="orientation|screenSize|smallestScreenSize|screenLayout|uiMode|keyboard|keyboardHidden" />

        <activity
            android:name="app.nimbusseat.client.MainActivity"
            android:label="NimbusSeat"
            android:exported="true"
            android:resizeableActivity="true"
            android:configChanges="orientation|screenSize|smallestScreenSize|screenLayout|uiMode|keyboard|keyboardHidden">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
                <category android:name="android.intent.category.LEANBACK_LAUNCHER" />
            </intent-filter>
        </activity>

    </application>"""
m = m.replace("</application>", activity, 1)
manifest.write_text(m)
print("patched", manifest)
