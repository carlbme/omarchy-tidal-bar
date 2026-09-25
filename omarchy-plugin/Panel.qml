import QtQuick
import QtQuick.Controls
import Quickshell.Io
import qs.Ui
import qs.Commons

Panel {
  id: root
  moduleName: "community.otidal"
  ipcTarget: "community.otidal"

  readonly property string otidal:
    Qt.resolvedUrl("bin/otidal").toString().replace(/^file:\/\//, "")
  readonly property color fg: bar ? bar.foreground : Color.foreground
  readonly property string fontFamily: bar ? bar.fontFamily : Style.font.family

  property string playbackState: "stopped"
  property string trackTitle: ""
  property string trackArtist: ""
  property string trackId: ""
  property string artworkUrl: ""
  property string trackQuality: ""
  property int queueIndex: -1
  property int queueLength: 0
  property bool radioOn: false
  property bool shuffleOn: false
  property bool favoriteOn: false
  property string listMode: "none"
  property string message: "Search, play favorites, or start radio."
  property var queueItems: []
  property var pendingAction: null

  ListModel { id: results }

  function cmd(args) {
    return [root.otidal].concat(args)
  }

  function refreshStatus() {
    if (!statusProc.running) statusProc.running = true
  }

  function runAction(args) {
    if (actionProc.running) {
      root.pendingAction = args
      return
    }
    actionProc.command = root.cmd(args)
    actionProc.running = true
  }

  function applyTrackPayload(payload) {
    if (!payload) return
    if (payload.error) {
      root.message = payload.error
      return
    }
    if (typeof payload.shuffle === "boolean") root.shuffleOn = payload.shuffle
    if (typeof payload.favorite === "boolean") root.favoriteOn = payload.favorite
    if (payload.track) {
      root.playbackState = payload.state || "playing"
      root.trackTitle = payload.track.title || ""
      root.trackArtist = payload.track.artist || ""
      root.trackId = String(payload.track.id || "")
      root.artworkUrl = String(payload.track.artwork_url || "")
      root.trackQuality = String(
              (payload.source && (payload.source.label || payload.source.quality))
              || payload.track.quality || "")
      if (typeof payload.index === "number") root.queueIndex = payload.index
      if (typeof payload.length === "number") root.queueLength = payload.length
      root.radioOn = payload.radio === true
    }
  }

  function clearResults() {
    results.clear()
    root.listMode = "none"
    if (!root.trackArtist) root.message = "Search, play favorites, or start radio."
  }

  function closeList() {
    if (root.listMode !== "queue")
      searchInput.text = ""
    root.clearResults()
  }

  function search() {
    var query = searchInput.text.trim()
    if (!query || searchProc.running) return
    root.message = "Searching…"
    searchProc.command = root.cmd(["search", query, "--limit", "8", "--json"])
    searchProc.running = true
  }

  function loadFavs() {
    if (searchProc.running) return
    root.message = "Loading favorites…"
    searchProc.command = root.cmd(["favs", "--limit", "12", "--json"])
    searchProc.running = true
  }

  function showQueue() {
    var wasQueue = root.listMode === "queue"
    var items = root.queueItems || []
    while (results.count > items.length)
      results.remove(results.count - 1)
    for (var i = 0; i < items.length; i++) {
      var row = {
        "selector": "jump:" + String(i),
        "title": String(items[i].title || ""),
        "artist": String(items[i].artist || ""),
        "kind": i === root.queueIndex ? "current" : "queued",
        "artworkUrl": String(items[i].artwork_url || "")
      }
      if (i < results.count)
        results.set(i, row)
      else
        results.append(row)
    }
    root.listMode = "queue"
    root.message = items.length ? "Queue" : "Queue is empty"
    if (!wasQueue)
      resultsFlick.contentY = 0
  }

  function playSelector(selector) {
    root.message = "Starting playback…"
    if (selector.indexOf("jump:") === 0) {
      runAction(["jump", String(Number(selector.slice(5)) + 1), "--json"])
      return
    }
    runAction(["play", selector, "--json"])
  }

  function queueSelector(selector) {
    if (selector.indexOf("jump:") === 0) return
    runAction(["queue", selector, "--json"])
  }

  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight
  onOpenedChanged: {
    if (opened) refreshStatus()
    else root.clearResults()
  }

  BarIconButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: ""
    iconComponent: Component {
      Item {
        TidalMark {
          anchors.centerIn: parent
          iconSize: Style.space(12)
          color: root.barForeground
        }
      }
    }
    onPressed: function(buttonCode) {
      if (buttonCode === Qt.MiddleButton) {
        root.runAction(["toggle", "--json"])
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
    contentWidth: panel.fittedContentWidth(Style.space(420))
    contentHeight: panel.fittedContentHeight(
                     header.implicitHeight
                     + (results.count > 0 ? resultsColumn.implicitHeight + content.spacing : 0),
                     Style.space(640))

    Column {
      id: content
      anchors.fill: parent
      spacing: Style.space(10)
      width: parent.width
      clip: true

      Column {
        id: header
        width: parent.width
        spacing: Style.space(10)

      Row {
        width: parent.width
        spacing: Style.space(10)

        Column {
          id: leftBlock
          width: parent.width - coverFrame.width - Style.space(10)
          spacing: Style.space(8)

          Column {
            width: parent.width
            spacing: Style.space(4)

            Text {
              width: parent.width
              text: root.trackTitle ? root.trackTitle : "TIDAL"
              color: root.fg
              font.family: root.fontFamily
              font.pixelSize: Style.font.subtitle
              font.bold: true
              elide: Text.ElideRight
            }

            Row {
              width: libraryRow.implicitWidth
              spacing: Style.space(8)

              Text {
                width: parent.width - queuePos.implicitWidth - (queuePos.visible ? Style.space(8) : 0)
                text: root.trackArtist ? root.trackArtist : root.message
                color: Qt.darker(root.fg, 1.35)
                font.family: root.fontFamily
                font.pixelSize: Style.font.body
                elide: Text.ElideRight
              }

              Text {
                id: queuePos
                visible: root.queueLength > 0 && root.queueIndex >= 0
                text: "[" + (root.queueIndex + 1) + "/" + root.queueLength + "]"
                color: Qt.darker(root.fg, 1.35)
                font.family: root.fontFamily
                font.pixelSize: Style.font.body
              }
            }

            Text {
              width: parent.width
              visible: root.trackTitle !== ""
              text: {
                var parts = []
                if (root.trackQuality) parts.push(root.trackQuality)
                if (root.radioOn) parts.push("radio")
                return parts.join("  ")
              }
              color: Qt.darker(root.fg, 1.6)
              font.family: root.fontFamily
              font.pixelSize: Style.font.caption
              elide: Text.ElideRight
            }
          }

          Row {
            spacing: Style.space(6)

            Button {
              text: "Prev"
              bordered: true
              foreground: root.fg
              fontFamily: root.fontFamily
              onClicked: root.runAction(["prev", "--json"])
            }
            Button {
              text: root.playbackState === "playing" ? "Pause" : "Play"
              bordered: true
              foreground: root.fg
              fontFamily: root.fontFamily
              onClicked: root.runAction(["toggle", "--json"])
            }
            Button {
              text: "Stop"
              bordered: true
              foreground: root.fg
              fontFamily: root.fontFamily
              onClicked: root.runAction(["stop", "--json"])
            }
            Button {
              text: "Next"
              bordered: true
              foreground: root.fg
              fontFamily: root.fontFamily
              onClicked: root.runAction(["next", "--json"])
            }
          }

          Row {
            id: libraryRow
            spacing: Style.space(6)

            Button {
              text: "Radio"
              bordered: true
              foreground: root.fg
              fontFamily: root.fontFamily
              opacity: (root.trackId !== "" || searchInput.text.trim() !== "") ? 1 : 0.4
              onClicked: {
                var seed = root.trackId !== "" ? ("t:" + root.trackId) : searchInput.text.trim()
                if (!seed) return
                root.runAction(["radio", seed, "--json"])
              }
            }
            Button {
              text: "Favorites"
              bordered: true
              foreground: root.fg
              fontFamily: root.fontFamily
              onClicked: root.loadFavs()
            }
            Button {
              text: "Queue"
              bordered: true
              foreground: root.fg
              fontFamily: root.fontFamily
              onClicked: root.showQueue()
            }
            Button {
              text: ""
              iconText: root.favoriteOn ? "󰋑" : "󰋕"
              tooltipText: root.favoriteOn ? "Remove from favorites" : "Add to favorites"
              bordered: true
              selected: root.favoriteOn
              foreground: root.fg
              fontFamily: root.fontFamily
              opacity: root.trackId !== "" ? 1 : 0.4
              onClicked: {
                if (root.trackId === "") return
                root.favoriteOn = !root.favoriteOn
                root.runAction(["favorite", "--json"])
              }
            }
          }
        }

        BorderSurface {
          id: coverFrame
          width: Style.space(124)
          height: Style.space(124)
          radius: Style.spacing.labelGap
          color: Style.normalFillFor(root.fg, Color.accent)
          borderSpec: Border.controlSpec("normal", root.fg, Color.accent)

          Image {
            anchors.fill: parent
            anchors.margins: Style.space(2)
            fillMode: Image.PreserveAspectCrop
            asynchronous: true
            source: root.artworkUrl
            visible: root.artworkUrl !== ""
          }

          Text {
            anchors.centerIn: parent
            visible: root.artworkUrl === ""
            text: "󰝚"
            color: root.fg
            font.family: root.fontFamily
            font.pixelSize: Style.font.displayLarge
          }
        }
      }

      Item {
        width: parent.width
        height: Math.max(searchInput.implicitHeight, searchBtn.implicitHeight)

        TextField {
          id: searchInput
          width: leftBlock.width
          anchors.left: parent.left
          anchors.verticalCenter: parent.verticalCenter
          placeholderText: "Search tracks, albums, playlists, artists"
          foreground: root.fg
          font.family: root.fontFamily
          onAccepted: root.search()
        }

        Button {
          id: searchBtn
          anchors.left: searchInput.right
          anchors.leftMargin: Style.space(10)
          anchors.right: parent.right
          anchors.verticalCenter: parent.verticalCenter
          text: searchProc.running ? "Searching…" : "Search"
          bordered: true
          foreground: root.fg
          fontFamily: root.fontFamily
          opacity: (!searchProc.running && searchInput.text.trim() !== "") ? 1 : 0.4
          onClicked: root.search()
        }
      }

      Row {
        width: searchInput.width
        spacing: Style.space(6)
        visible: results.count > 0

        Button {
          width: (parent.width - parent.spacing) / 2
          text: "Shuffle"
          bordered: true
          selected: root.shuffleOn
          foreground: root.fg
          fontFamily: root.fontFamily
          opacity: root.listMode === "queue" ? 1 : 0.4
          onClicked: {
            if (root.listMode !== "queue") return
            root.runAction(["shuffle", "--json"])
          }
        }
        Button {
          width: (parent.width - parent.spacing) / 2
          text: "Close List"
          bordered: true
          foreground: root.fg
          fontFamily: root.fontFamily
          onClicked: root.closeList()
        }
      }
      }

      Flickable {
        id: resultsFlick
        width: parent.width
        visible: results.count > 0
        height: visible ? Math.max(0, content.height - header.height - content.spacing) : 0
        contentWidth: width
        contentHeight: resultsColumn.implicitHeight
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        flickableDirection: Flickable.VerticalFlick
        interactive: contentHeight > height
        ScrollBar.vertical: ScrollBar {
          policy: ScrollBar.AsNeeded
        }

        Column {
          id: resultsColumn
          width: resultsFlick.width - (resultsFlick.contentHeight > resultsFlick.height ? Style.space(12) : 0)
          spacing: Style.space(4)

        Repeater {
          model: results

          Item {
            required property string selector
            required property string title
            required property string artist
            required property string kind
            required property string artworkUrl
            width: parent.width
            height: Math.max(plusBtn.implicitHeight, Style.space(28))

            Image {
              id: rowArt
              width: Style.space(28)
              height: Style.space(28)
              anchors.left: parent.left
              anchors.verticalCenter: parent.verticalCenter
              fillMode: Image.PreserveAspectCrop
              asynchronous: true
              source: artworkUrl
              visible: artworkUrl !== ""
            }

            Button {
              id: playBtn
              anchors.left: rowArt.visible ? rowArt.right : parent.left
              anchors.leftMargin: rowArt.visible ? Style.space(6) : 0
              anchors.right: plusBtn.visible ? plusBtn.left : parent.right
              anchors.rightMargin: plusBtn.visible ? Style.space(6) : 0
              anchors.top: parent.top
              anchors.bottom: parent.bottom
              leftAlign: true
              clip: true
              bordered: true
              foreground: root.fg
              fontFamily: root.fontFamily
              text: ""
              property bool hovering: false
              readonly property string label: {
                if (kind === "current") return "▶  " + artist + " — " + title
                if (kind === "track" || kind === "queued") return artist + " — " + title
                return kind + "  " + title
              }
              onHovered: function(isHovered) { hovering = isHovered }
              onClicked: root.playSelector(selector)

              Item {
                id: labelClip
                anchors.fill: parent
                anchors.leftMargin: playBtn.leftPadding
                anchors.rightMargin: playBtn.rightPadding
                clip: true
                readonly property bool overflowing: labelText.implicitWidth > width + 1

                Text {
                  id: labelText
                  anchors.verticalCenter: parent.verticalCenter
                  text: playBtn.label
                  color: root.fg
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.body
                }

                SequentialAnimation {
                  running: playBtn.hovering && labelClip.overflowing && labelClip.width > 8
                  loops: Animation.Infinite
                  onRunningChanged: if (!running) labelText.x = 0

                  PauseAnimation { duration: 220 }
                  NumberAnimation {
                    target: labelText
                    property: "x"
                    to: Math.min(0, labelClip.width - labelText.implicitWidth)
                    duration: Math.max(2800, (labelText.implicitWidth - labelClip.width) * 45)
                    easing.type: Easing.Linear
                  }
                  PauseAnimation { duration: 1100 }
                  NumberAnimation {
                    target: labelText
                    property: "x"
                    to: 0
                    duration: 700
                    easing.type: Easing.InOutQuad
                  }
                }
              }
            }

            Button {
              id: plusBtn
              anchors.right: parent.right
              anchors.verticalCenter: parent.verticalCenter
              text: "+"
              bordered: true
              foreground: root.fg
              fontFamily: root.fontFamily
              visible: selector.indexOf("jump:") !== 0
              onClicked: root.queueSelector(selector)
            }
          }
        }
        }
      }
    }
  }

  Timer {
    interval: 2000
    running: root.opened || root.playbackState === "playing"
    repeat: true
    onTriggered: root.refreshStatus()
  }

  Process {
    id: statusProc
    command: root.cmd(["status", "--json"])
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        try {
          var payload = JSON.parse(text || "{}")
          root.playbackState = payload.state || "stopped"
          root.trackTitle = payload.track ? payload.track.title || "" : ""
          root.trackArtist = payload.track ? payload.track.artist || "" : ""
          root.trackId = payload.track ? String(payload.track.id || "") : ""
          root.artworkUrl = payload.track ? String(payload.track.artwork_url || "") : ""
          root.trackQuality = payload.track ? String(payload.track.quality || "") : ""
          root.queueIndex = typeof payload.index === "number" ? payload.index : -1
          root.queueItems = payload.queue || []
          root.queueLength = root.queueItems.length
          root.radioOn = payload.radio === true
          root.shuffleOn = payload.shuffle === true
          root.favoriteOn = payload.favorite === true
          if (payload.error && !payload.available) root.message = payload.error
          if (root.listMode === "queue") root.showQueue()
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
          var count = 0
          var tracks = payload.tracks || []
          for (var i = 0; i < tracks.length; i++) {
            results.append({
              "selector": "t:" + String(tracks[i].id),
              "title": String(tracks[i].title || ""),
              "artist": String(tracks[i].artist || ""),
              "kind": "track",
              "artworkUrl": String(tracks[i].artwork_url || "")
            })
            count++
          }
          function addEntries(items, kind, prefix) {
            for (var j = 0; j < (items || []).length; j++) {
              results.append({
                "selector": prefix + String(items[j].id),
                "title": String(items[j].title || items[j].artist || ""),
                "artist": String(items[j].artist || ""),
                "kind": kind,
                "artworkUrl": String(items[j].artwork_url || "")
              })
              count++
            }
          }
          addEntries(payload.albums, "album", "a:")
          addEntries(payload.playlists, "playlist", "p:")
          addEntries(payload.artists, "artist", "r:")
          root.listMode = "search"
          root.message = count ? "Select a result" : "No results"
          resultsFlick.contentY = 0
        } catch (error) {
          root.message = "Search failed."
        }
      }
    }
  }

  Process {
    id: actionProc
    command: []
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        try {
          var payload = JSON.parse(text || "{}")
          root.applyTrackPayload(payload)
          if (payload && payload.state === "playing" && root.listMode === "search")
            root.clearResults()
          if (root.listMode === "queue") root.showQueue()
        } catch (error) {
        }
      }
    }
    onRunningChanged: {
      if (!running) {
        root.refreshStatus()
        if (root.pendingAction) {
          var next = root.pendingAction
          root.pendingAction = null
          root.runAction(next)
        }
      }
    }
  }
}
