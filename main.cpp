#include <iomanip>
#include <iostream>
#include <memory>
#include <thread>
#include <sys/mman.h>
#include <libcamera/libcamera.h>
#include <libcamera/base/shared_fd.h>
#include <opencv2/opencv.hpp>

#include "event_loop.h"


using namespace libcamera;
using namespace std::chrono_literals;

static const int PREBUFFER_FRAMES = 150;	// ~10s at 15fps
static const double MOTION_THRESHOLD = 25.0;	// motion sensitivity
static const int POST_MOTION_FRAMES = 150;	// record 10s after motion stops
static const int FRAME_WIDTH = 1920, FRAME_HEIGHT = 1080, FPS = 15;

static std::shared_ptr<Camera> camera;
static EventLoop loop;
static Stream *stream = nullptr;
static unsigned int stride;
static std::map<int, std::pair<void *, unsigned int>> mappedBuffers;
static cv::VideoWriter writer;
//static int postCount = 0;
//static cv::Mat lastGray;

/*
TODO:
--width 1920
--height 1080
--fps 15
--pre 5   // Seconds (or maybe frames) to capture before event
--post 60 // How much to capture after event. If threshold is triggered again within this time, it will continue recording
--threshold xxx
--out /mnt/video
*/


// Converts libcamera buffer to OpenCV Mat (YUV -> greyscale)
cv::Mat bufferToMat(const FrameBuffer *buffer, int width, int height) {
	// Y plane (index 0) is all we care about, it contains the greyscale information
	const FrameBuffer::Plane &plane = buffer->planes()[0];
	
	void *data = mappedBuffers[plane.fd.get()].first;
	cv::Mat image(height, width, CV_8UC1, data, stride);
	return image;
}


static void processRequest(Request *request) {
	if (!writer.isOpened()) {
		std::string filename = "/mnt/video/" + std::to_string(std::time(nullptr)) + ".avi";
		writer.open(filename, cv::VideoWriter::fourcc('Y','8','0','0'), FPS, {FRAME_WIDTH, FRAME_HEIGHT}, false);
	}
	cv::Mat frame = bufferToMat(request->buffers().begin()->second, FRAME_WIDTH, FRAME_HEIGHT);
	writer.write(frame);
	/*
	
	// motion detection
	cv::Mat diff;
	if (!lastGray.empty()) {
		cv::absdiff(frame, lastGray, diff);
		double motion = cv::mean(diff)[0];
		if (motion > MOTION_THRESHOLD) {
			if (!recording) {
				std::string filename = "/mnt/video/" + std::to_string(std::time(nullptr)) + ".avi";
				writer.open(filename, cv::VideoWriter::fourcc('M','J','P','G'), FPS, {FRAME_WIDTH, FRAME_HEIGHT}, true);
				for (auto &f : prebuffer) {
					writer.write(f);
				}
				prebuffer.clear();
				recording = true;
				postCount = POST_MOTION_FRAMES;
				std::cout << "Motion start: " << filename << "\n";
			}
			else {
				postCount = POST_MOTION_FRAMES;
			}
		}
	}
	lastGray = frame.clone();

	if (recording) {
		writer.write(frame);
		if (--postCount <= 0) {
			writer.release();
			recording = false;
			std::cout << "Motion end\n";
		}
	}
	else {
		prebuffer.push_back(frame);
		if (prebuffer.size() > PREBUFFER_FRAMES)
			prebuffer.pop_front();
	}
	*/

	request->reuse(Request::ReuseBuffers);
	camera->queueRequest(request); // Re-queue for next frame
}


/*
 * This function is invoked in the CameraManager's thread, so avoid any heavy processing here.
 * Re-direct processing to the application's thread instead, so as not to block the CameraManager's
 * thread for large amount of time.
 */
static void requestComplete(Request *request) {
	if (request->status() == Request::RequestCancelled) {
		return;
	}
	loop.callLater(std::bind(&processRequest, request));
}


void printConfig(const StreamConfiguration &config) {
	std::cout << "  size = " << config.size.toString() << std::endl;
	std::cout << "  stride = " << config.stride << std::endl;
	std::cout << "  frameSize = " << config.frameSize << std::endl;
	std::cout << "  bufferCount = " << config.bufferCount << std::endl;
	std::cout << "  pixelFormat = " << config.pixelFormat.toString() << std::endl;
	if (config.colorSpace) {
		std::cout << "  colorSpace = " << config.colorSpace->toString() << std::endl;
	}
}


int main() {
	CameraManager cm;
	cm.start();

	if (cm.cameras().empty()) {
		std::cerr << "No cameras were identified on the system" << std::endl;
		cm.stop();
		return EXIT_FAILURE;
	}

	camera = cm.get(cm.cameras()[0]->id());
	camera->acquire();

	std::unique_ptr<CameraConfiguration> config = camera->generateConfiguration({ StreamRole::VideoRecording });
	StreamConfiguration &streamConfig = config->at(0);
	streamConfig.size = { FRAME_WIDTH, FRAME_HEIGHT };
	streamConfig.pixelFormat = formats::NV12;  // YUV 4:2:0 image with a plane of 8 bit Y samples followed by an interleaved U/V plane.
	config->validate();
	std::cout << "Validated camera configuration:" << std::endl;
	printConfig(streamConfig);
	camera->configure(config.get());
	stream = streamConfig.stream();
	stride = streamConfig.stride;

	FrameBufferAllocator *allocator = new FrameBufferAllocator(camera);
	if (allocator->allocate(stream) < 0) {
		std::cerr << "Can't allocate buffers" << std::endl;
		return -ENOMEM;
	}
	size_t allocated = allocator->buffers(stream).size();
	std::cout << "Allocated " << allocated << " buffers for stream" << std::endl;
		  
	std::vector<std::unique_ptr<Request>> requests;
	for (const std::unique_ptr<FrameBuffer> &buffer : allocator->buffers(stream)) {
		std::unique_ptr<Request> request = camera->createRequest();
		if (!request) {
			std::cerr << "Can't create request" << std::endl;
			return -ENOMEM;
		}
		int ret = request->addBuffer(stream, buffer.get());
		if (ret < 0) {
			std::cerr << "Can't set buffer for request" << std::endl;
			return ret;
		}
		for (const FrameBuffer::Plane &plane : buffer->planes()) {
			void *memory = mmap(nullptr, plane.length, PROT_READ, MAP_SHARED, plane.fd.get(), 0);
			mappedBuffers[plane.fd.get()] = std::make_pair(memory, plane.length);
		}
		requests.push_back(std::move(request));
	}

	camera->requestCompleted.connect(requestComplete);
	camera->start();
	for (auto &request : requests) {
		camera->queueRequest(request.get());
	}

	/*
	 * Run the EventLoop
	 *
	 * In order to dispatch events received from the video devices, such
	 * as buffer completions, an event loop has to be run.
	 */
	std::cout << "Running." << std::endl;
	loop.timeout(10);
	int ret = loop.exec();
	std::cout << "Exited event loop with status: " << ret << std::endl;
	std::cout << "Stopping camera." << std::endl;
	camera->requestCompleted.disconnect(requestComplete);
	camera->stop();
	writer.release();
	for (auto &iter : mappedBuffers) {
		std::pair<void *, unsigned int> pair = iter.second;
		munmap(std::get<0>(pair), std::get<1>(pair));
	}
	allocator->free(stream);
	delete allocator;
	camera->release();
	camera.reset();
	cm.stop();

	return 0;
}
