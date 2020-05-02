/*
	signjson tool

	Copyright (c) 2020 past-due (https://github.com/past-due)

	Permission is hereby granted, free of charge, to any person obtaining a copy
	of this software and associated documentation files (the "Software"), to deal
	in the Software without restriction, including without limitation the rights
	to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
	copies of the Software, and to permit persons to whom the Software is
	furnished to do so, subject to the following conditions:

	The above copyright notice and this permission notice shall be included in all
	copies or substantial portions of the Software.

	THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
	IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
	FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
	AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
	LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
	OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
	SOFTWARE.
*/

#include <iostream>
#include <string>
#include <args.hxx>
#include <EmbeddedJSONSignature.h>
#include <memory>
#include <cstdio>
#include <cerrno>
#include <exception>

void close_file(std::FILE* fp) { std::fclose(fp); }

static std::string loadFileToString(const std::string& filepath)
{
	std::FILE* fp = std::fopen(filepath.c_str(), "rb");
	if (!fp) {
		int error = errno;
		std::cerr << "Failed to open file (" << error << "): " << filepath << std::endl;
		return "";
	}

	auto f_ptr = std::unique_ptr<std::FILE, decltype(&close_file)>(fp, &close_file);

	if (std::fseek(fp, 0, SEEK_END) < 0) {
		std::cerr << "fseek[SEEK_END] failed" << std::endl;
		return "";
	}

	const long size = std::ftell(fp);
	if (size <= 0) {
		std::cerr << "std::ftell returned size: " << size << std::endl;
		return "";
	}

	if (std::fseek(fp, 0, SEEK_SET) < 0) {
		std::cerr << "fseek[SEEK_SET] failed" << std::endl;
		return "";
	}

	std::string result;
	result.resize(size);

	const auto size_read = std::fread(const_cast<char*>(result.data()), 1, size, fp);
	result.resize(size_read);

	return result;
}

static bool saveStringToFile(const std::string& str, const std::string& filepath)
{
	std::FILE* fp = std::fopen(filepath.c_str(), "wb");
	if (!fp) { return false; }
	const auto size_written = std::fwrite(str.data(), 1, str.size(), fp);
	if (size_written != str.size())
	{
		std::fclose(fp);
		return false;
	}
	if (std::fclose(fp) != 0)
	{
		// std::fclose failed?
		return false;
	}
	return true;
}

int
main(int argc, char **argv)
{
	args::ArgumentParser parser("Sign a JSON file using EmbeddedJSONSignature.", "");
    args::HelpFlag help(parser, "help", "Display this help menu", {'h', "help"});
    args::ValueFlag<std::string> secretkey(parser, "secretkey", "The base64-encoded secretkey", {'k'});
    args::PositionalList<std::string> jsonfiles(parser, "jsonfiles", "A list of json files to sign");
    try
    {
        parser.ParseCLI(argc, argv);
    }
    catch (args::Help)
    {
        std::cout << parser;
        return 0;
    }
    catch (args::ParseError e)
    {
        std::cerr << e.what() << std::endl;
        std::cerr << parser;
        return 1;
    }
    catch (args::ValidationError e)
    {
        std::cerr << e.what() << std::endl;
        std::cerr << parser;
        return 1;
    }
    if (!secretkey)
	{
		std::cerr << "Missing required secretkey parameter" << std::endl;
		return 1;
	}
	std::string b64_secretKey = args::get(secretkey);
	bool failedAFile = false;
    if (jsonfiles)
	{
		for (const auto filename: args::get(jsonfiles))
		{
			std::string originalJson = loadFileToString(filename);
			if (originalJson.empty())
			{
				std::cerr << "File is empty / does not exist / could not be loaded: " << filename << std::endl;
				failedAFile = true;
				continue;
			}
			std::string signedJson;
			try
			{
				signedJson = EmbeddedJSONSignature::signJson(originalJson, b64_secretKey);
			}
			catch (const std::exception& e)
			{
				std::cerr << "Failed to sign file \"" << filename << "\" with error: " << e.what() << std::endl;
				failedAFile = true;
				continue;
			}
			if (!saveStringToFile(signedJson, filename))
			{
				std::cerr << "Failed to save signed file: " << filename << std::endl;
				failedAFile = true;
				continue;
			}
			std::cout << "Signed file: " << filename << std::endl;
		}
	}
	if (failedAFile)
	{
		return 1;
	}
	return 0;
}
