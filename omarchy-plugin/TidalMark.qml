import QtQuick
import QtQuick.Shapes
import qs.Commons

Item {
  id: root

  property real iconSize: Style.font.icon
  property color color: Color.foreground

  // Press-kit mark is 141.73×94.49 (~3:2). Fit that into the bar slot.
  width: iconSize * 1.5
  height: iconSize
  implicitWidth: width
  implicitHeight: height

  Shape {
    anchors.fill: parent
    antialiasing: true
    layer.enabled: true
    layer.samples: 4

    Diamond { cx: root.width * 0.499; cy: root.height * 0.249 }
    Diamond { cx: root.width * 0.499; cy: root.height * 0.746 }
    Diamond { cx: root.width * 0.168; cy: root.height * 0.249 }
    Diamond { cx: root.width * 0.831; cy: root.height * 0.249 }
  }

  component Diamond: ShapePath {
    property real cx: 0
    property real cy: 0
    readonly property real hw: root.width * 0.166
    readonly property real hh: root.height * 0.249

    fillColor: root.color
    strokeWidth: 0
    startX: cx
    startY: cy - hh
    PathLine { x: cx + hw; y: cy }
    PathLine { x: cx; y: cy + hh }
    PathLine { x: cx - hw; y: cy }
    PathLine { x: cx; y: cy - hh }
  }
}
