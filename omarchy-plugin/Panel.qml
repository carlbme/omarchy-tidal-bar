import QtQuick
import QtQuick.Controls
import Quickshell
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
  property bool statusLoaded: false
  property bool loggedIn: false
  readonly property bool dimmed: statusLoaded && !loggedIn
  property string loginState: "none"
  property string loginUrl: ""
  property string lastToastedTrackId: ""
  property bool statusSeen: false
  property bool toastOpen: false
  readonly property int rowHeight: Style.space(28)
  readonly property int listSpacing: Style.space(4)
  readonly property int listContentHeight: results.count > 0
    ? Math.min(results.count * rowHeight + Math.max(0, results.count - 1) * listSpacing, Style.space(640))
    : 0
  property var queueItems: []
  property var pendingAction: null
  property string pendingListMode: "search"
  property bool shuffleFavsPending: false

  ListModel { id: results }

  function cmd(args) {
    return [root.otidal].concat(args)
  }

  function refreshStatus() {
    if (!statusProc.running) statusProc.running = true
  }

  function barWindow() {
    var qs = root.QsWindow
    return qs ? qs.window : null
  }

  function noteTrackChange() {
    if (!root.loggedIn) {
      root.lastToastedTrackId = ""
      root.statusSeen = false
      return
    }
    if (!root.statusSeen) {
      root.statusSeen = true
      root.lastToastedTrackId = root.trackId
      return
    }
    if (root.trackId && root.trackId !== root.lastToastedTrackId) {
      root.lastToastedTrackId = root.trackId
      if (!root.opened && root.visible && barWindow())
        root.toastOpen = true
    }
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
    if (payload.state === "pending") {
      root.loginState = "pending"
      root.loginUrl = String(payload.url || "")
      root.message = "Log in at the URL above, then paste the 'Oops' page URL."
      return
    }
    if (payload.logged_in === true) {
      root.loggedIn = true
      root.statusLoaded = true
      root.loginState = "none"
      root.loginUrl = ""
      redirectInput.text = ""
      root.message = "Logged in."
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
    if (!root.loggedIn) return
    var query = searchInput.text.trim()
    if (!query || searchProc.running) return
    root.message = "Searching…"
    root.pendingListMode = "search"
    searchProc.command = root.cmd(["search", query, "--limit", "8", "--json"])
    searchProc.running = true
  }

  function loadFavs() {
    if (!root.loggedIn || searchProc.running) return
    root.message = "Loading favorites…"
    root.pendingListMode = "favs"
    searchProc.command = root.cmd(["favs", "--limit", "1000", "--json"])
    searchProc.running = true
  }

  function startLogin() {
    if (!root.dimmed || root.loginState === "pending") return
    root.message = "Log in in your browser. The code expires quickly — paste the 'Oops' page URL right away."
    root.runAction(["login", "start", "--json"])
  }

  function finishLogin() {
    var url = redirectInput.text.trim()
    if (!url) return
    root.message = "Finishing login…"
    root.runAction(["login", "finish", "--redirect", url, "--json"])
  }

  function toggleFavorite() {
    if (!root.loggedIn || root.trackId === "") return
    root.favoriteOn = !root.favoriteOn
    root.runAction(["favorite", "--json"])
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
      resultsList.contentY = 0
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

  function queueIndexOfSelector(selector) {
    if (selector.indexOf("t:") !== 0) return -1
    var id = selector.slice(2)
    for (var i = 0; i < root.queueItems.length; i++)
      if (String(root.queueItems[i].id) === id) return i
    return -1
  }

  function removeQueueItem(index) {
    root.message = "Removing from queue…"
    runAction(["remove", String(index + 1), "--json"])
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
                     + (results.count > 0 ? root.listContentHeight + content.spacing : 0),
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

            Item {
              id: titleClip
              width: parent.width
              height: titleText.implicitHeight
              clip: true
              property bool hovering: false
              readonly property bool overflowing: titleText.implicitWidth > width + 1

              MouseArea {
                anchors.fill: parent
                hoverEnabled: true
                onEntered: titleClip.hovering = true
                onExited: titleClip.hovering = false
              }

              Text {
                id: titleText
                width: parent.width
                text: root.trackTitle ? root.trackTitle : "TIDAL"
                color: root.fg
                font.family: root.fontFamily
                font.pixelSize: Style.font.subtitle
                font.bold: true
                elide: titleClip.hovering ? Text.ElideNone : Text.ElideRight
              }

              SequentialAnimation {
                running: titleClip.hovering && titleClip.overflowing && titleClip.width > 8
                loops: Animation.Infinite
                onRunningChanged: if (!running) titleText.x = 0

                PauseAnimation { duration: 220 }
                NumberAnimation {
                  target: titleText
                  property: "x"
                  to: Math.min(0, titleClip.width - titleText.implicitWidth)
                  duration: Math.max(2800, (titleText.implicitWidth - titleClip.width) * 45)
                  easing.type: Easing.Linear
                }
                PauseAnimation { duration: 1100 }
                NumberAnimation {
                  target: titleText
                  property: "x"
                  to: 0
                  duration: 700
                  easing.type: Easing.InOutQuad
                }
              }
            }

            Row {
              width: libraryRow.implicitWidth
              spacing: Style.space(8)

              Text {
                width: parent.width - queuePos.implicitWidth - (queuePos.visible ? Style.space(8) : 0)
                text: root.dimmed ? "" : (root.trackArtist ? root.trackArtist : root.message)
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
            visible: !root.dimmed

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
            visible: !root.dimmed

            Button {
              text: "Radio"
              bordered: true
              foreground: root.fg
              fontFamily: root.fontFamily
              opacity: root.loggedIn && (root.trackId !== "" || searchInput.text.trim() !== "") ? 1 : 0.4
              onClicked: {
                if (!root.loggedIn) return
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
              opacity: root.queueLength > 0 ? 1 : 0.4
              onClicked: {
                if (root.queueLength === 0) return
                root.showQueue()
              }
            }
          }

          Column {
            id: loginArea
            width: parent.width
            visible: root.dimmed
            spacing: Style.space(6)

            Row {
              spacing: Style.space(6)
              visible: root.loginState !== "pending"

              Button {
                text: "Login"
                bordered: true
                foreground: root.fg
                fontFamily: root.fontFamily
                onClicked: root.startLogin()
              }
              Text {
                anchors.verticalCenter: parent.verticalCenter
                text: "Opens TIDAL in your browser."
                color: Qt.darker(root.fg, 1.6)
                font.family: root.fontFamily
                font.pixelSize: Style.font.caption
              }
            }

            Column {
              width: parent.width
              visible: root.loginState === "pending"
              spacing: Style.space(6)

              Text {
                width: parent.width
                text: root.loginUrl
                color: Qt.darker(root.fg, 1.6)
                font.family: root.fontFamily
                font.pixelSize: Style.font.caption
                elide: Text.ElideRight
              }

              Row {
                width: parent.width
                spacing: Style.space(6)

                TextField {
                  id: redirectInput
                  width: parent.width - finishBtn.implicitWidth - Style.space(6)
                  placeholderText: "Paste the full 'Oops' page URL (or just the code)"
                  foreground: root.fg
                  font.family: root.fontFamily
                  onAccepted: root.finishLogin()
                }
                Button {
                  id: finishBtn
                  text: "Finish"
                  bordered: true
                  foreground: root.fg
                  fontFamily: root.fontFamily
                  opacity: redirectInput.text.trim() !== "" ? 1 : 0.4
                  onClicked: root.finishLogin()
                }
              }
            }

            Text {
              id: loginMessage
              width: parent.width
              visible: root.message !== ""
              text: root.message
              wrapMode: Text.WordWrap
              color: Qt.darker(root.fg, 1.35)
              font.family: root.fontFamily
              font.pixelSize: Style.font.body
            }
          }
        }

        BorderSurface {
          id: coverFrame
          visible: !root.dimmed
          width: root.dimmed ? 0 : Style.space(124)
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

          MouseArea {
            id: coverHover
            anchors.fill: parent
            enabled: root.loggedIn && root.trackId !== ""
            hoverEnabled: enabled
            cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
            onClicked: root.toggleFavorite()

            Text {
              id: heartShadow
              x: heartIcon.x + 1
              y: heartIcon.y + 1
              visible: heartIcon.visible
              text: root.favoriteOn ? "󰋑" : "󰋕"
              color: "black"
              opacity: 0.25
              font.family: root.fontFamily
              font.pixelSize: coverFrame.height * 0.75
            }
            Text {
              id: heartIcon
              anchors.centerIn: parent
              visible: coverHover.enabled && coverHover.containsMouse
              text: root.favoriteOn ? "󰋑" : "󰋕"
              color: root.fg
              opacity: 0.35
              font.family: root.fontFamily
              font.pixelSize: coverFrame.height * 0.75
            }
          }
        }
      }

      Item {
        width: parent.width
        height: Math.max(searchInput.implicitHeight, searchBtn.implicitHeight)
        visible: !root.dimmed

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
        visible: results.count > 0 && !root.dimmed

        Button {
          width: (parent.width - parent.spacing) / 2
          text: "Shuffle"
          bordered: true
          selected: root.shuffleOn
          foreground: root.fg
          fontFamily: root.fontFamily
          opacity: (root.listMode === "queue" || root.listMode === "favs") ? 1 : 0.4
          onClicked: {
            if (root.listMode === "favs") {
              root.shuffleFavsPending = true
              root.message = "Queuing favorites and shuffling…"
              root.runAction(["shuffle", "favs", "--json"])
              return
            }
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

      ListView {
        id: resultsList
        width: parent.width
        visible: results.count > 0 && !root.dimmed
        height: visible ? Math.max(0, content.height - header.height - content.spacing) : 0
        clip: true
        spacing: root.listSpacing
        model: results
        ScrollBar.vertical: ScrollBar {
          policy: ScrollBar.AsNeeded
        }

        delegate: Item {
          required property string selector
          required property string title
          required property string artist
          required property string kind
          required property string artworkUrl
          readonly property bool inQueue: root.queueIndexOfSelector(selector) >= 0
          width: resultsList.width
          height: root.rowHeight

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
              height: parent.height
              text: (root.listMode === "queue" || inQueue) ? "−" : "+"
              tooltipText: (root.listMode === "queue" || inQueue) ? "Remove from queue" : "Add to queue"
              bordered: true
              foreground: root.fg
              fontFamily: root.fontFamily
              visible: root.listMode === "queue" ? true : selector.indexOf("jump:") !== 0
              onClicked: {
                if (selector.indexOf("jump:") === 0)
                  root.removeQueueItem(Number(selector.slice(5)))
                else if (inQueue)
                  root.removeQueueItem(root.queueIndexOfSelector(selector))
                else
                  root.queueSelector(selector)
              }
            }
          }
      }
    }
  }

  PopupCard {
    id: nowPlayingToast
    anchorItem: button
    bar: root.bar
    owner: root
    triggerMode: "hover"
    open: root.toastOpen
    contentWidth: Style.space(320)
    contentHeight: Style.space(68)

    Row {
      anchors.centerIn: parent
      width: parent.width
      spacing: Style.space(10)

      BorderSurface {
        id: toastCover
        anchors.verticalCenter: parent.verticalCenter
        width: Style.space(56)
        height: Style.space(56)
        radius: Style.spacing.labelGap
        color: Style.normalFillFor(root.fg, Color.accent)

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
          font.pixelSize: Style.font.body
        }
      }

      Column {
        anchors.verticalCenter: parent.verticalCenter
        width: parent.width - toastCover.width - parent.spacing
        spacing: Style.space(2)

        Text {
          width: parent.width
          text: root.trackTitle
          color: root.fg
          font.family: root.fontFamily
          font.pixelSize: Style.font.subtitle
          font.bold: true
          elide: Text.ElideRight
        }

        Text {
          width: parent.width
          text: root.trackArtist
          color: Qt.darker(root.fg, 1.35)
          font.family: root.fontFamily
          font.pixelSize: Style.font.body
          elide: Text.ElideRight
        }
      }
    }

    MouseArea {
      anchors.fill: parent
      cursorShape: Qt.PointingHandCursor
      onClicked: {
        root.toastOpen = false
        root.toggle()
      }
    }
  }

  Timer {
    interval: 4000
    running: root.toastOpen
    onTriggered: root.toastOpen = false
  }

  Timer {
    interval: 2000
    running: true
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
          root.statusLoaded = true
          root.loggedIn = payload.logged_in === true
          if (root.loggedIn) {
            root.loginState = "none"
            root.loginUrl = ""
            redirectInput.text = ""
            if (!payload.available) root.message = "Player stopped."
          } else if (root.loginState === "none" && !actionProc.running) {
            root.message = "Not logged in."
          }
          if (root.listMode === "queue") root.showQueue()
          root.noteTrackChange()
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
          root.listMode = root.pendingListMode
          root.pendingListMode = "search"
          root.message = count ? "Select a result" : "No results"
          resultsList.contentY = 0
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
          if (root.shuffleFavsPending) {
            root.shuffleFavsPending = false
            if (!payload || !payload.error) root.showQueue()
          }
          if (root.listMode === "queue") root.showQueue()
        } catch (error) {
          root.message = "otidal returned no valid response."
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
