project('pimotion', 'cpp', 
	default_options : [
		'werror=true',
		'warning_level=2',
		'cpp_std=c++17',
	])

src_files = files([
	'main.cpp',
	'event_loop.cpp',
])

deps = [
	dependency('libcamera', required : true),
	dependency('opencv4', required : true),
	dependency('libevent_pthreads'),
]

cpp_arguments = [ '-Wno-unused-parameter', ]
add_project_arguments(cpp_arguments, language : 'cpp')

executable('pimotion', src_files, dependencies : deps)
