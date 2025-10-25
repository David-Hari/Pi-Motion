project('pimotion', 'cpp', default_options : ['cpp_std=c++17'])

libcamera_dep = dependency('libcamera', required : true)
opencv_dep = dependency('opencv4', required : true)

executable('pimotion',
	['main.cpp'],
	dependencies : [libcamera_dep, opencv_dep]
)