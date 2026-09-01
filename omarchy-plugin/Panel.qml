import QtQuick
import QtQuick.Controls
import Quickshell.Io
import qs.Ui
import qs.Commons

Panel {
  id: root
  moduleName: "community.otidal"
  ipcTarget: "community.otidal"

  property string playbackState: "stopped"
  property string trackTitle: ""
  property string trackArtist: ""
  property string message: "Run otidal login in a terminal to get started."

  ListModel { id: results }

  function refreshStatus() {
    if (!statusProc.running) statusProc.running = true
  }

  function search() {
    var query = searchInput.text.trim()
    if (!query || searchProc.running) return
    root.message = "Searching…"
    searchProc.command = ["otidal", "search", query, "--limit", "8", "--json"]
    searchProc.running = true
  }

  function playTrack(trackId) {
    actionProc.command = ["otidal", "play", "t:" + trackId, "--json"]
    actionProc.running = true
  }

  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight
  onOpenedChanged: if (opened) refreshStatus()

  BarIconButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: "󰓇"
    onPressed: function(buttonCode) {
      if (buttonCode === Qt.MiddleButton) {
        actionProc.command = ["otidal", "toggle", "--json"]
        actionProc.running = true
      } else {
        root.toggle()
      }
    }
  }

  KeyboardPanel {
    id: panel
    anchorItem: button
    owner: root
    bar: root.bar
    open: root.opened
    contentWidth: panel.fittedContentWidth(Style.space(390))
    contentHeight: panel.fittedContentHeight(content.implicitHeight, Style.space(560))

    Column {
      id: content
      anchors.fill: parent
      spacing: Style.space(10)

      Text {
        width: parent.width
        text: root.trackTitle ? root.trackTitle : "TIDAL"
        color: root.bar ? root.bar.foreground : Color.foreground
        font.family: root.bar ? root.bar.fontFamily : Style.font.family
        font.pixelSize: Style.font.subtitle
        font.bold: true
        elide: Text.ElideRight
      }

      Text {
        width: parent.width
        text: root.trackArtist || root.message
        color: Qt.darker(root.bar ? root.bar.foreground : Color.foreground, 1.35)
        font.family: root.bar ? root.bar.fontFamily : Style.font.family
        font.pixelSize: Style.font.body
        wrapMode: Text.WordWrap
      }

      Row {
        spacing: Style.space(6)

        Button {
          text: root.playbackState === "playing" ? "Pause" : "Play"
          onClicked: {
            actionProc.command = ["otidal", "toggle", "--json"]
            actionProc.running = true
          }
        }

        Button {
          text: "Stop"
          onClicked: {
            actionProc.command = ["otidal", "stop", "--json"]
            actionProc.running = true
          }
        }
      }

      TextField {
        id: searchInput
        width: parent.width
        placeholderText: "Search TIDAL"
        onAccepted: root.search()
      }

      Button {
        text: searchProc.running ? "Searching…" : "Search"
        enabled: !searchProc.running && searchInput.text.trim() !== ""
        onClicked: root.search()
      }

      Column {
        width: parent.width
        spacing: Style.space(4)

        Repeater {
          model: results

          Button {
            required property string trackId
            required property string title
            required property string artist
            width: parent.width
            text: artist + " — " + title
            onClicked: root.playTrack(trackId)
          }
        }
      }
    }
  }

  Process {
    id: statusProc
    command: ["otidal", "status", "--json"]
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        try {
          var payload = JSON.parse(text || "{}")
          root.playbackState = payload.state || "stopped"
          root.trackTitle = payload.track ? payload.track.title || "" : ""
          root.trackArtist = payload.track ? payload.track.artist || "" : ""
          if (payload.error && !payload.available) root.message = payload.error
        } catch (error) {
          root.message = "otidal is not installed or returned invalid status."
        }
      }
    }
  }

  Process {
    id: searchProc
    command: []
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        results.clear()
        try {
          var payload = JSON.parse(text || "{}")
          if (payload.error) {
            root.message = payload.error
            return
          }
          var tracks = payload.tracks || []
          for (var i = 0; i < tracks.length; i++) {
            results.append({
              "trackId": String(tracks[i].id),
              "title": String(tracks[i].title || ""),
              "artist": String(tracks[i].artist || "")
            })
          }
          root.message = tracks.length ? "Select a track" : "No results"
        } catch (error) {
          root.message = "Search failed."
        }
      }
    }
  }

  Process {
    id: actionProc
    command: []
    stdout: StdioCollector { waitForEnd: true }
    onRunningChanged: if (!running) root.refreshStatus()
  }
}
