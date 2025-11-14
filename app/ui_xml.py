_ui_xml = r'''<?xml version="1.0" encoding="UTF-8"?>
<ui version="4.0">
 <class>MainWindow</class>
 <widget class="QMainWindow" name="MainWindow">
  <property name="windowTitle"><string>Laser Scene Editor</string></property>
  <widget class="QWidget" name="centralwidget">
   <layout class="QVBoxLayout" name="verticalLayout">
    <item>
     <widget class="QTabWidget" name="tabWidget"><property name="tabsClosable"><bool>true</bool></property></widget>
    </item>
    <item>
     <widget class="QSplitter" name="splitter"><property name="orientation"><enum>Qt::Horizontal</enum></property>
      <widget class="QWidget" name="rightPane">
       <layout class="QVBoxLayout" name="v2">
        <item>
         <widget class="QTableWidget" name="elementsTable"><property name="columnCount"><number>7</number></property></widget>
        </item>
       </layout>
      </widget>
     </widget>
    </item>
   </layout>
  </widget>
  <widget class="QMenuBar" name="menubar"/><widget class="QStatusBar" name="statusbar"/>
 </widget>
 <resources/>
 <connections/>
</ui>
'''